import braintree
from django.conf import settings
from django.http import HttpRequest
from django.shortcuts import render, redirect, get_object_or_404

from .tasks import payment_completed
from orders.models import Order
from shop.recommender import Recommender

gateway = braintree.BraintreeGateway(settings.BRAINTREE_CONF)


def payment_process(request: HttpRequest):
    order_id = request.session.get('order_id')
    order: Order = get_object_or_404(Order, pk=order_id)
    total_cost = order.get_total_cost()

    if request.method == 'POST':
        nonce = request.POST.get('payment_method_nonce', None)
        result = gateway.transaction.sale({
            'amount': f'{total_cost:.2f}',
            'payment_method_nonce': nonce,
            'options': {
                'submit_for_settlement': True,
            },
        })
        if result.is_success:
            r = Recommender()
            r.products_bought(order.items.all())
            order.paid = True
            order.braintree_id = result.transaction.id
            order.save()
            payment_completed.delay(order.pk)
            return redirect('payment:done')
        else:
            return redirect('payment:canceled')
    else:
        client_token = gateway.client_token.generate()

        context = {
            'order': order,
            'client_token': client_token,
        }
        return render(request, 'payment/process.html', context)


def payment_done(request: HttpRequest):
    return render(request, 'payment/done.html')


def payment_canceled(request: HttpRequest):
    return render(request, 'payment/canceled.html')
