from django.shortcuts import render
from .forms import UserRegisterForm, CustomLoginForm
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from django.views.generic.edit import CreateView
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from order.models import Order


class SignUpView(CreateView):
    template_name = "users/register.html"
    success_url = reverse_lazy("users:login")
    form_class = UserRegisterForm


class MyLoginView(LoginView):
    template_name = "users/login.html"
    success_url = reverse_lazy("store:products")
    form_class = CustomLoginForm

    # redirect authenticated user to the products page
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(reverse("store:products"))
        return super(LoginView, self).get(request, *args, **kwargs)


def logout_view(request):
    logout(request)
    return redirect("store:products")


@login_required(login_url="users:login")
def my_orders(request):
    """Display orders for authenticated user"""
    customer = request.user.customer
    # orders query set - list of orders
    orders = Order.objects.filter(customer=customer, complete=True).order_by(
        "-date_modified"
    )
    return render(request, "users/orders.html", context={"orders": orders})
