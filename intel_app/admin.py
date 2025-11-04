import re
from datetime import datetime

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.utils.html import format_html
from import_export import resources, fields

from . import models
from import_export.admin import ExportActionMixin

from .models import TopUpRequest


# Register your models here.
class CustomUserAdmin(ExportActionMixin, UserAdmin):
    list_display = ['first_name', 'last_name', 'username', 'email', 'wallet', 'phone', 'status']

    fieldsets = (
        *UserAdmin.fieldsets,
        (
            'Other Personal info',
            {
                'fields': (
                    'phone', 'wallet', 'status'
                )
            }
        )
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'wallet')
        }),)


class TransactionAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ['user', 'bundle_number', 'offer', 'amount', 'reference', 'transaction_status', 'transaction_date',
                    'action_buttons']
    search_fields = ['reference', 'bundle_number', 'user__username']
    list_filter = ['transaction_status', 'user']
    actions = ['mark_selected_as_completed', 'mark_selected_as_pending', 'mark_selected_as_processing',
               'mark_selected_as_failed', 'refund_selected_transactions']

    def action_buttons(self, obj):
        buttons = []
        status_actions = {
            "Pending": "pending",
            "Completed": "complete",
            "Processing": "processing",
            "Failed": "failed",
            "Canceled and Refunded": "refund"
        }

        for status, url_suffix in status_actions.items():
            if obj.transaction_status != status:
                action_url = f'{url_suffix}/{obj.pk}/'
                color = "#007bff" if status == "Processing" else "#ffc107" if status == "Pending" else "#28a745" if status == "Completed" else "#dc3545"
                buttons.append(
                    f'<a class="button" href="{action_url}" style="padding: 5px 10px; background-color: {color}; color: white; border-radius: 3px; text-decoration: none;">{status}</a>')

        return format_html(' '.join(buttons))

    action_buttons.short_description = 'Actions'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('complete/<int:transaction_id>/', self.admin_site.admin_view(self.set_transaction_completed),
                 name='complete_transaction'),
            path('pending/<int:transaction_id>/', self.admin_site.admin_view(self.set_transaction_pending),
                 name='pending_transaction'),
            path('processing/<int:transaction_id>/', self.admin_site.admin_view(self.set_transaction_processing),
                 name='processing_transaction'),
            path('failed/<int:transaction_id>/', self.admin_site.admin_view(self.set_transaction_failed),
                 name='failed_transaction'),
            path('refund/<int:transaction_id>/', self.admin_site.admin_view(self.refund_transaction),
                 name='refund_transaction'),
        ]
        return custom_urls + urls

    def set_transaction_status(self, request, transaction_id, status, message):
        transaction_obj = get_object_or_404(self.model, pk=transaction_id)
        if transaction_obj.transaction_status == status:
            self.message_user(request, f"This transaction is already {status}.", level=messages.WARNING)
        else:
            transaction_obj.transaction_status = status
            transaction_obj.save()
            self.message_user(request, message, level=messages.SUCCESS)
        return redirect('..')

    def set_transaction_completed(self, request, transaction_id, *args, **kwargs):
        return self.set_transaction_status(request, transaction_id, 'Completed', "Transaction marked as completed.")

    def set_transaction_pending(self, request, transaction_id, *args, **kwargs):
        return self.set_transaction_status(request, transaction_id, 'Pending', "Transaction marked as pending.")

    def set_transaction_processing(self, request, transaction_id, *args, **kwargs):
        return self.set_transaction_status(request, transaction_id, 'Processing', "Transaction marked as processing.")

    def set_transaction_failed(self, request, transaction_id, *args, **kwargs):
        return self.set_transaction_status(request, transaction_id, 'Failed', "Transaction marked as failed.")

    # Bulk actions
    def mark_selected_as_completed(self, request, queryset):
        self.update_transaction_status(request, queryset, 'Completed', "Marked {} transactions as completed.")

    mark_selected_as_completed.short_description = "Mark selected as Completed"

    def mark_selected_as_pending(self, request, queryset):
        self.update_transaction_status(request, queryset, 'Pending', "Marked {} transactions as pending.")

    mark_selected_as_pending.short_description = "Mark selected as Pending"

    def mark_selected_as_processing(self, request, queryset):
        self.update_transaction_status(request, queryset, 'Processing', "Marked {} transactions as processing.")

    mark_selected_as_processing.short_description = "Mark selected as Processing"

    def mark_selected_as_failed(self, request, queryset):
        self.update_transaction_status(request, queryset, 'Failed', "Marked {} transactions as failed.")

    mark_selected_as_failed.short_description = "Mark selected as Failed"

    def update_transaction_status(self, request, queryset, status, message):
        updated_count = queryset.exclude(transaction_status=status).update(transaction_status=status)
        self.message_user(request, message.format(updated_count), level=messages.SUCCESS)

    def refund_transaction(self, request, transaction_id, *args, **kwargs):
        transaction_obj = get_object_or_404(self.model, pk=transaction_id)
        if transaction_obj.transaction_status == 'Canceled and Refunded':
            self.message_user(request, "This transaction has already been refunded.", level=messages.WARNING)
            return redirect('..')

        user = transaction_obj.user
        amount = transaction_obj.amount
        try:
            with transaction.atomic():
                user.wallet += amount
                user.save()
                transaction_obj.transaction_status = 'Canceled and Refunded'
                transaction_obj.save()

                models.WalletTransactionn.objects.create(
                    user=user,
                    transaction_type='Credit',
                    transaction_amount=amount,
                    transaction_use='Refund',
                    new_balance=user.wallet,
                )
                self.message_user(request,
                                  f"Transaction refunded and GHS{amount} credited back to {user.username}'s wallet.",
                                  level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"An error occurred: {str(e)}", level=messages.ERROR)
        return redirect('..')

    def refund_transaction(self, request, transaction_id, *args, **kwargs):
        transaction_obj = get_object_or_404(self.model, pk=transaction_id)
        if transaction_obj.transaction_status == 'Canceled and Refunded':
            self.message_user(request, "This transaction has already been refunded.", level=messages.WARNING)
            return redirect('..')
        user = transaction_obj.user
        amount = transaction_obj.amount
        try:
            with transaction.atomic():
                user.wallet += amount
                user.save()
                transaction_obj.transaction_status = 'Canceled and Refunded'
                transaction_obj.save()

                models.WalletTransactionn.objects.create(
                    user=user,
                    transaction_type='Credit',
                    transaction_amount=amount,
                    transaction_use='Refund',
                    new_balance=user.wallet,
                )
                self.message_user(request, f"Transaction refunded and GHS{amount} credited back to {user.username}'s wallet.", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"An error occurred: {str(e)}", level=messages.ERROR)
        return redirect('..')

    def mark_selected_as_completed(self, request, queryset):
        not_completed = queryset.exclude(transaction_status='Completed')
        updated_count = not_completed.update(transaction_status='Completed')
        self.message_user(request, f"Marked {updated_count} transactions as completed.", level=messages.SUCCESS)
    mark_selected_as_completed.short_description = "Mark selected transactions as completed"

    def refund_selected_transactions(self, request, queryset):
        not_refunded = queryset.exclude(transaction_status='Canceled and Refunded')
        try:
            with transaction.atomic():
                for transaction_obj in not_refunded:
                    user = transaction_obj.user
                    amount = transaction_obj.amount
                    user.wallet += amount
                    user.save()
                    transaction_obj.transaction_status = 'Canceled and Refunded'
                    transaction_obj.save()

                    models.WalletTransactionn.objects.create(
                        user=user,
                        transaction_type='Credit',
                        transaction_amount=amount,
                        transaction_use='Transaction Refund',
                        new_balance=user.wallet,
                    )
                self.message_user(request, f"Refunded {not_refunded.count()} transactions and credited amounts back to users' wallets.", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"An error occurred: {str(e)}", level=messages.ERROR)
    refund_selected_transactions.short_description = "Refund selected transactions"

    @staticmethod
    def _format_offer_for_export(offer_str: str) -> str:
        if not offer_str:
            return ""
        # normalize
        s = str(offer_str).upper().replace(" ", "")
        # pull leading number (allow decimal, just in case)
        m = re.match(r"([\d]+(?:\.\d+)?)", s)
        if not m:
            return offer_str  # fallback untouched if it doesn't match
        val = float(m.group(1))

        if val >= 1000:
            gb = val / 1000.0
            # tidy decimals (e.g., 2.00 -> 2, 1.50 -> 1.5)
            txt = f"{gb:.2f}".rstrip("0").rstrip(".")
            return f"{txt}"
        # < 1000: return the numeric MB amount with no unit (per your ask to remove 'MB')
        # If you prefer "500MB" instead, change to: return f"{int(val) if val.is_integer() else val}MB"
        return f"{int(val) if val.is_integer() else val}"

    # Provide a dynamic resource class so this works for ALL concrete transaction models
    def get_export_resource_class(self):
        admin_self = self

        class TxnResource(resources.ModelResource):
            # Override `offer` column
            offer = fields.Field(column_name="offer")

            def dehydrate_offer(self, obj):
                return admin_self._format_offer_for_export(getattr(obj, "offer", ""))

            class Meta:
                model = admin_self.model  # important: bind to the concrete model of each subclassed admin
                # include the fields you want in export (you can tweak this)
                fields = (
                    "id",
                    "user__username",
                    "bundle_number",
                    "offer",
                    "amount",
                    "reference",
                    "transaction_status",
                    "transaction_date",
                )
                export_order = (
                    "id",
                    "user__username",
                    "bundle_number",
                    "offer",
                    "amount",
                    "reference",
                    "transaction_status",
                    "transaction_date",
                )

        return TxnResource


@admin.register(models.IShareBundleTransaction)
class IShareBundleTransactionAdmin(TransactionAdmin):
    pass


@admin.register(models.MTNTransaction)
class MTNTransactionAdmin(TransactionAdmin):
    pass


class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'reference', 'transaction_date', 'amount']


class TopUpRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'reference', 'amount', 'date', 'status', 'credit_user_button']
    list_filter = ['status', 'date']
    actions = ['credit_selected_users']

    def credit_user_button(self, obj):
        if not obj.status:
            return format_html(
                '<a class="button" href="{}" style="padding: 5px 10px; background-color: #28a745; color: white; border-radius: 3px; text-decoration: none;">Credit User</a>',
                f'credit/{obj.pk}/'
            )
        return "Already Credited"

    credit_user_button.short_description = 'Action'
    credit_user_button.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('credit/<int:topup_id>/', self.admin_site.admin_view(self.credit_user), name='credit-user'),
        ]
        return custom_urls + urls

    def credit_user(self, request, topup_id, *args, **kwargs):
        topup_request = get_object_or_404(TopUpRequest, pk=topup_id)

        if topup_request.status:
            self.message_user(request, "This transaction has already been credited.", level=messages.WARNING)
            return redirect('..')

        try:
            with transaction.atomic():
                user = topup_request.user
                user.wallet += topup_request.amount
                user.save()

                topup_request.status = True
                topup_request.credited_at = datetime.now()
                topup_request.payment_channel = "Manual"
                topup_request.save()

                models.WalletTransactionn.objects.create(
                    user=user,
                    transaction_type='Credit',
                    transaction_amount=topup_request.amount,
                    transaction_use='Wallet Topup (Admin)',
                    new_balance=user.wallet,
                )
                # response = requests.request('POST', url=sms_url, params=sms_body, headers=sms_headers)
                # print(response.text)
                self.message_user(request, f"Successfully credited {topup_request.amount} to {user.username}.",
                                  level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"An error occurred: {str(e)}", level=messages.ERROR)

        return redirect('..')

    def credit_selected_users(self, request, queryset):
        pending_requests = queryset.filter(status=False)
        if not pending_requests.exists():
            self.message_user(request, "No pending transactions selected.", level=messages.WARNING)
            return

        try:
            with transaction.atomic():
                # Group pending requests by user to optimize wallet updates
                user_requests = {}
                for request_obj in pending_requests:
                    user = request_obj.user
                    if user in user_requests:
                        user_requests[user].append(request_obj)
                    else:
                        user_requests[user] = [request_obj]

                for user, requests_list in user_requests.items():
                    total_amount = sum(req.amount for req in requests_list)
                    user.wallet += total_amount
                    user.save()

                    for req in requests_list:
                        req.status = True
                        req.credited_at = datetime.now()
                        req.payment_channel = "Manual"
                        req.save()

                    models.WalletTransactionn.objects.create(
                        user=user,
                        transaction_type='Credit',
                        transaction_amount=total_amount,
                        transaction_use='Wallet Topup (Admin)',
                        new_balance=user.wallet,
                    )

                self.message_user(request, f"Successfully credited {pending_requests.count()} transactions.",
                                  level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"An error occurred: {str(e)}", level=messages.ERROR)

    credit_selected_users.short_description = "Credit selected top-up requests"


@admin.register(models.AFARegistration)
class AFARegistrationAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = [
        'user', 'phone_number', 'gh_card_number', 'name', 'amount',
        'reference', 'transaction_status', 'transaction_date', 'action_buttons'
    ]
    search_fields = ['user__username', 'phone_number', 'gh_card_number', 'name', 'reference']
    actions = ['mark_selected_as_completed', 'refund_selected_transactions']

    def action_buttons(self, obj):
        buttons = []
        if obj.transaction_status != 'Completed':
            complete_url = f'complete/{obj.pk}/'
            buttons.append(f'<a class="button" href="{complete_url}" style="padding: 5px 10px; background-color: #28a745; color: white; border-radius: 3px; text-decoration: none;">Complete</a>')
        if obj.transaction_status != 'Canceled and Refunded':
            refund_url = f'refund/{obj.pk}/'
            buttons.append(f'<a class="button" href="{refund_url}" style="padding: 5px 10px; background-color: #dc3545; color: white; border-radius: 3px; text-decoration: none;">Refund</a>')
        return format_html(' '.join(buttons))
    action_buttons.short_description = 'Actions'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('complete/<int:pk>/', self.admin_site.admin_view(self.complete_transaction), name='afa_complete_transaction'),
            path('refund/<int:pk>/', self.admin_site.admin_view(self.refund_transaction), name='afa_refund_transaction'),
        ]
        return custom_urls + urls

    def complete_transaction(self, request, pk, *args, **kwargs):
        afa_registration = get_object_or_404(models.AFARegistration, pk=pk)
        if afa_registration.transaction_status == 'Completed':
            self.message_user(request, "This transaction is already completed.", level=messages.WARNING)
            return redirect('..')
        afa_registration.transaction_status = 'Completed'
        afa_registration.save()
        self.message_user(request, "Transaction marked as completed.", level=messages.SUCCESS)
        return redirect('..')

    def refund_transaction(self, request, pk, *args, **kwargs):
        afa_registration = get_object_or_404(models.AFARegistration, pk=pk)
        if afa_registration.transaction_status == 'Canceled and Refunded':
            self.message_user(request, "This transaction has already been refunded.", level=messages.WARNING)
            return redirect('..')
        user = afa_registration.user
        amount = afa_registration.amount
        try:
            with transaction.atomic():
                user.wallet += amount
                user.save()
                afa_registration.transaction_status = 'Canceled and Refunded'
                afa_registration.save()

                models.WalletTransactionn.objects.create(
                    user=user,
                    transaction_type='Credit',
                    transaction_amount=amount,
                    transaction_use='Afa Transaction Refund',
                    new_balance=user.wallet,
                )
                self.message_user(
                    request,
                    f"Transaction refunded and GHS{amount} credited back to {user.username}'s wallet.",
                    level=messages.SUCCESS
                )
        except Exception as e:
            self.message_user(request, f"An error occurred: {str(e)}", level=messages.ERROR)
        return redirect('..')

    def mark_selected_as_completed(self, request, queryset):
        not_completed = queryset.exclude(transaction_status='Completed')
        updated_count = not_completed.update(transaction_status='Completed')
        self.message_user(request, f"Marked {updated_count} transactions as completed.", level=messages.SUCCESS)
    mark_selected_as_completed.short_description = "Mark selected transactions as completed"

    def refund_selected_transactions(self, request, queryset):
        not_refunded = queryset.exclude(transaction_status='Canceled and Refunded')
        try:
            with transaction.atomic():
                for afa_registration in not_refunded:
                    user = afa_registration.user
                    amount = afa_registration.amount
                    user.wallet += amount
                    user.save()
                    afa_registration.transaction_status = 'Canceled and Refunded'
                    afa_registration.save()

                    models.WalletTransactionn.objects.create(
                        user=user,
                        transaction_type='Credit',
                        transaction_amount=amount,
                        transaction_use='Afa Transaction Refund',
                        new_balance=user.wallet,
                    )
                self.message_user(
                    request,
                    f"Refunded {not_refunded.count()} transactions and credited amounts back to users' wallets.",
                    level=messages.SUCCESS
                )
        except Exception as e:
            self.message_user(request, f"An error occurred: {str(e)}", level=messages.ERROR)
    refund_selected_transactions.short_description = "Refund selected transactions"


@admin.register(models.VodafoneTransaction)
class TelecelTransactionAdmin(TransactionAdmin):
    pass


admin.site.register(models.CustomUser, CustomUserAdmin)
admin.site.register(models.IshareBundlePrice)
admin.site.register(models.MTNBundlePrice)
admin.site.register(models.Payment, PaymentAdmin)
admin.site.register(models.AdminInfo)
admin.site.register(models.TopUpRequest, TopUpRequestAdmin)
admin.site.register(models.AgentIshareBundlePrice)
admin.site.register(models.AgentMTNBundlePrice)
admin.site.register(models.SuperAgentBigTimeBundlePrice)
admin.site.register(models.SuperAgentMTNBundlePrice)
admin.site.register(models.SuperAgentIshareBundlePrice)
admin.site.register(models.BigTimeTransaction)
admin.site.register(models.BigTimeBundlePrice)
admin.site.register(models.AgentBigTimeBundlePrice)
admin.site.register(models.AgentVodaBundlePrice)
admin.site.register(models.SuperAgentVodaBundlePrice)
admin.site.register(models.VodaBundlePrice)
admin.site.register(models.WalletTransactionn)


