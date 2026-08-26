import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.orders.models import Order

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
)
def send_order_created_email(order_id):
    """
    Notify a tenant's configured recipients that an order was created.

    Uses Order.unscoped deliberately: the worker has no request context, so the
    access scope defaults to DenyAll and Order.objects would return nothing.
    See apps.tenants.scope.
    """
    try:
        order = (
            Order.unscoped.select_related("event", "client")
            .prefetch_related("event__lines")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        logger.warning("send_order_created_email: Order %s no longer exists, skipping.", order_id)
        return

    # Independent customers have no tenant, so there is no tenant-level
    # recipient list to read. Nothing to notify.
    if order.client is None:
        logger.info(
            "send_order_created_email: order %s belongs to an independent customer "
            "(no tenant), no notification configured, skipping.",
            order_id,
        )
        return

    recipients = order.client.order_notification_emails
    if not recipients:
        logger.warning(
            "send_order_created_email: tenant %s (%s) has no order_notification_emails "
            "configured, skipping order %s.",
            order.client_id,
            order.client.name,
            order_id,
        )
        return

    lines = order.event.lines.all()
    line_rows = [
        {
            "name": line.product_name_snapshot,
            "qty": line.qty,
            "unit_price_display": f"{line.unit_price_cents_snapshot / 100:.2f}",
            "line_total_display": f"{line.qty * line.unit_price_cents_snapshot / 100:.2f}",
        }
        for line in lines
    ]
    total_cents = sum(line.qty * line.unit_price_cents_snapshot for line in lines)

    context = {
        "order": order,
        "event": order.event,
        "tenant": order.client,
        "line_rows": line_rows,
        "total_display": f"{total_cents / 100:.2f}",
    }
    body = render_to_string("orders/emails/order_created.txt", context)
    subject = f"Nueva orden creada — {order.event.title}"

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )
