from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Assets,Notify_Manager,Notify_Employee,AssetsIssuance
from .forms import AssetForm
from .filters import AssetsFilter
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
import requests,json
from django.templatetags.static import static
from django.contrib import messages
from main_app.models import CustomUser

LOCATION_CHOICES = (
    ("Main Room" , "Main Room"),
    ("Meeting Room", "Meeting Room"),
    ("Main Office", "Main Office"),
)

class AssetsListView(LoginRequiredMixin, ListView):
    template_name = 'asset_app/home.html'
    ordering = ['-asset_added_date']

    def get_queryset(self):
        user = self.request.user
        if user.user_type in ['1', '2']:
            self.model = Assets
            print(user.user_type)

            return Assets.objects.all().order_by('-asset_added_date')
        else:
            self.model = AssetsIssuance
            print(user.user_type)
            return AssetsIssuance.objects.filter(asset_assignee=user).order_by('-date_issued')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset_list'] = context.get('object_list')
        context['is_employee'] = self.request.user.user_type == '3' 
        return context
        
    
class AssetsDetailView(DetailView):
    model = Assets
    template_name = 'asset_app/asset_detail.html'
    context_object_name = 'asset'


class AssetsCreateView(LoginRequiredMixin, CreateView):
    model = Assets
    fields = [
        'asset_name',
        'asset_brand', 
        'asset_serial_No',
        'asset_condition',
        'ip_address',
        'os_version',
        'asset_image',
        'manager'
    ]
    template_name = 'asset_app/assets_form.html'  
    success_url = reverse_lazy('asset_app:assets-list')

    def form_valid(self, form):
        form.instance.manager = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.user_type == "1" or self.request.user.is_superuser:
            context['allManager'] = CustomUser.objects.filter(user_type=2)
        context['current_user'] = self.request.user
        return context
    
    

class AssetUpdateView(UpdateView):
    model = Assets
    form_class = AssetForm
    template_name = 'asset_app/asset_update.html'
    context_object_name = 'asset'

    def get_success_url(self):
        return reverse_lazy('asset_app:assets-detail', kwargs={'pk': self.object.pk})
    
    

class AssetDeleteView(View):
    def get(self, request, pk):
        asset = get_object_or_404(Assets, pk=pk)
        asset.delete()
        return redirect('asset_app:assets-list')
    


class AssetAssignView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Assets
    fields = ['asset_assignee']
    template_name = 'asset_app/asset_assign.html'

    def test_func(self):
        return str(self.request.user.user_type) in ['2', '3']

    def get_success_url(self):
        return reverse('asset_app:assets-detail', kwargs={'pk': self.object.pk})



class AssetClaimView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login_page")
    
    def handle_no_permission(self):
        messages.warning(self.request, "Please log in to access this page.")
        return redirect(self.login_url)

    def get(self, request):
        user = request.user
        # Manager View
        if user.user_type == '2':  
            template_name = 'manager_template/manager_claim.html'
            unclaimed_assets = Assets.objects.filter(is_asset_issued=False)

            pending_requests = Notify_Manager.objects.filter(
                asset__in=unclaimed_assets,
                manager__isnull=False,
                approved__isnull=True  
            ).values_list('asset_id', flat=True)

            print(unclaimed_assets)
            print(pending_requests)

            return render(request, template_name, {
                'assets': unclaimed_assets,
                'page_title': 'Claim Asset',
            })
        
         # employee view
        else:
            template_name = 'asset_app/asset_claim.html'
            unclaimed_assets = Assets.objects.filter(is_asset_issued=False)
            claimed_assets = AssetsIssuance.objects.filter(asset_assignee=request.user)   
           
            pending_requests = Notify_Manager.objects.filter(
                asset__in=unclaimed_assets,
                manager__isnull=False,
                 approved__isnull=True
            ).values_list('asset_id', flat=True)

            return render(request, template_name, {
                'unclaimed_assets': unclaimed_assets,
                'claimed_assets': claimed_assets,
                'pending_requests': list(pending_requests),
                'page_title': 'Claim Asset',
            })
        

    def post(self, request, *args, **kwargs):
        user = request.user

        asset_id = request.POST.get('asset_id')
        asset = get_object_or_404(Assets, id=asset_id)

        if asset.is_asset_issued:
            messages.warning(request, "This asset has already been claimed.")
            return redirect('asset_app:asset-claim')

        try:
            manager_message = request.POST.get('message', 'Requesting asset approval.')
            manager = asset.manager

            Notify_Manager.objects.create(
                manager=manager,
                employee=user,
                asset=asset,
                message=manager_message,
                approved = None
            )

            if hasattr(manager, 'fcm_token') and manager.fcm_token:
                body = {
                    'notification': {
                        'title': "OfficeOps - Asset Request",
                        'body': manager_message,
                        'click_action': reverse('manager_view_notification'),
                        'icon': static('dist/img/AdminLTELogo.png')
                    },
                    'to': manager.fcm_token
                }

                headers = {
                    'Authorization': 'key=YOUR_FIREBASE_SERVER_KEY', 
                    'Content-Type': 'application/json'
                }

                response = requests.post(
                    "https://fcm.googleapis.com/fcm/send",
                    data=json.dumps(body),
                    headers=headers
                )

                if response.status_code != 200:
                    print(f"FCM error: {response.content}")

            messages.success(request, "Your asset request has been sent for approval.")

        except Exception as e:
            print(f"Notification error: {e}")
            messages.error(request, "Failed to send asset request.")

        return redirect('asset_app:asset-claim')

   
  

class AssetUnclaimView(LoginRequiredMixin, View):
    def post(self, request, asset_id):
        asset = get_object_or_404(Assets, id=asset_id, asset_assignee=request.user)
        asset.asset_assignee = None
        asset.asset_issued = False
        asset.save()
        messages.success(request, f"You have unclaimed the asset: {asset.asset_name}")
        return redirect('asset_app:asset-claim')




