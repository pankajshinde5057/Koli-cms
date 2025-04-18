from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Assets,Notify_Manager,Notify_Employee
from .forms import AssetForm
from .filters import AssetsFilter
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
import requests,json
from django.templatetags.static import static
from django.contrib import messages


class AssetsListView(ListView):
    model = Assets
    template_name = 'asset_app/asset_list.html'
    context_object_name = 'assets'
    ordering = ['-date_purchased']

    def get_queryset(self):
        if self.request.user: 
            return Assets.objects.all()
        return Assets.objects.filter(asset_assignee=self.request.user)
        

class AssetsDetailView(DetailView):
    model = Assets
    template_name = 'asset_app/asset_detail.html'
    context_object_name = 'asset'
    
    

class AssetsCreateView(LoginRequiredMixin, CreateView):
    model = Assets
    fields = ['asset_name', 'asset_serial_No', 'asset_manufacturer', 'asset_issued', 'asset_image', 'manager']
    success_url = reverse_lazy('asset_app:assets-list')

    def form_valid(self, form):
        return super().form_valid(form)
    
    

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
    template_name = 'asset_app/asset_claim.html'
    login_url = reverse_lazy("login_page")

    def handle_no_permission(self):
        messages.warning(self.request, "Please log in to access this page.")
        return redirect(self.login_url)
    
    def get(self, request):
        if request.user.user_type == '2':
            template_name = 'manager_template/manager_claim.html'
            unclaimed_assets = Assets.objects.filter(asset_assignee__isnull=True)

            return render(request, template_name, {
                'assests': unclaimed_assets,
                'page_title': 'Claim Asset',
            })

        # Default employee view
        else:
            unclaimed_assets = Assets.objects.filter(asset_assignee__isnull=True)
            claimed_assets = Assets.objects.filter(asset_assignee=request.user)   
           
            template_name = 'asset_app/asset_claim.html'
            pending_requests = Notify_Manager.objects.filter(
                asset__in=unclaimed_assets,
                asset__asset_assignee__isnull=True,
                manager__isnull=False,
                approved=None
            ).values_list('asset_id', flat=True)

            return render(request, template_name, {
                'unclaimed_assets': unclaimed_assets,
                'claimed_assets': claimed_assets,
                'pending_requests': list(pending_requests),
                'page_title': 'Claim Asset',
            })


    def post(self, request, *args, **kwargs):
        asset_id = request.POST.get('asset_id')
        asset = get_object_or_404(Assets, id=asset_id)
        if asset.asset_assignee:
            messages.warning(request, "Asset has already been claimed.")
            return redirect('asset_app:claim-asset')
        
        if request.user.user_type == '2':
            asset.asset_assignee = request.user
            asset.save()
            messages.success(request, "You have successfully claimed the asset.")
            return redirect('asset_app:asset-claim')
       
        try:
            manager = asset.manager
            manager_message = request.POST.get("message")

            Notify_Manager.objects.create(
                manager = manager,
                employee = request.user,
                asset = asset,
                message = manager_message,
                approved = None
            )
            if hasattr(manager, 'fcm_token') and manager.fcm_token:
                body = {
                    'notification': {
                        'title': "OfficeOps - Asset Claimed",
                        'body': manager_message,
                        'click_action': reverse('manager_view_notification'),
                        'icon': static('dist/img/AdminLTELogo.png')
                    },
                    'to': manager.fcm_token
                }
                fcm_url = "https://fcm.googleapis.com/fcm/send"
                headers = {
                    'Authorization': 'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                    'Content-Type': 'application/json'
                }
                requests.post(fcm_url, data=json.dumps(body), headers=headers)

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




