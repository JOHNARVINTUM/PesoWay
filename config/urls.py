from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from payments.views import PaymentIntentDetailView, PaymentIntentListCreateView, PaymentIntentCancelView
from webhooks.views import WebhookEndpointListCreateView, WebhookEventListView
from transactions.views import RefundCreateView, TransactionListView
from dashboard.views import merchant_dashboard, test_console
from simulator.views import SimulatedAttemptCompleteView, SimulatedAttemptCreateView
from accounts.views import LoginView, LogoutView
from merchants.views import APIKeyCreateView, APIKeyRevokeView
from simulator.checkout_views import hosted_checkout
from dashboard.public_views import developer_docs, home

urlpatterns = [
    path("", home, name="home"),
    path("developers/", developer_docs, name="developer-docs"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/payment-intents/", PaymentIntentListCreateView.as_view(), name="payment-intent-list"),
    path("api/v1/auth/login/", LoginView.as_view(), name="login"),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/v1/merchant/api-keys/", APIKeyCreateView.as_view(), name="api-key-create"),
    path("api/v1/merchant/api-keys/<int:key_id>/revoke/", APIKeyRevokeView.as_view(), name="api-key-revoke"),
    path("api/v1/payment-intents/<uuid:public_id>/", PaymentIntentDetailView.as_view(), name="payment-intent-detail"),
    path("api/v1/payment-intents/<uuid:public_id>/cancel/", PaymentIntentCancelView.as_view(), name="payment-intent-cancel"),
    path("api/v1/webhook-endpoints/", WebhookEndpointListCreateView.as_view(), name="webhook-endpoint-list"),
    path("api/v1/webhook-events/", WebhookEventListView.as_view(), name="webhook-event-list"),
    path("api/v1/transactions/", TransactionListView.as_view(), name="transaction-list"),
    path("api/v1/refunds/", RefundCreateView.as_view(), name="refund-create"),
    path("api/v1/payment-intents/<uuid:public_id>/attempts/", SimulatedAttemptCreateView.as_view(), name="simulated-attempt-create"),
    path("api/v1/simulator/payment-attempts/<uuid:reference>/complete/", SimulatedAttemptCompleteView.as_view(), name="simulated-attempt-complete"),
    path("checkout/<uuid:public_id>/", hosted_checkout, name="hosted-checkout"),
    path("dashboard/", merchant_dashboard, name="merchant-dashboard"),
    path("dashboard/test-console/", test_console, name="test-console"),
]

