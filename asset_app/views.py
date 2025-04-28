from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Assets,Notify_Manager,Notify_Employee,AssetsIssuance, AssetCategory, AssetAssignmentHistory
from .forms import AssetForm
from .filters import AssetsFilter
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
import requests,json
from django.templatetags.static import static
from django.contrib import messages
from main_app.models import CustomUser
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.utils import timezone


LOCATION_CHOICES = (
    ("Main Room" , "Main Room"),
    ("Meeting Room", "Meeting Room"),
    ("Main Office", "Main Office"),
)


class AssetsListView(ListView):
    model = Assets
    template_name = 'asset_app/home.html'
    context_object_name = 'assets'
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Employee
        if user.user_type == '3': 
            issued_assets = AssetsIssuance.objects.filter(
                asset_assignee=user
            ).values_list('asset_id', flat=True)
            queryset = queryset.filter(id__in=issued_assets)
        
        # Apply search filter
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(asset_name__icontains=search) |
                Q(asset_serial_number__icontains=search) |
                Q(asset_brand__icontains=search)
            )
        
        # Apply status filter
        status = self.request.GET.get('status')
        if status == 'issued':
            queryset = queryset.filter(is_asset_issued=True)
        elif status == 'available':
            queryset = queryset.filter(is_asset_issued=False)
        
        # Apply category filter
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(asset_category_id=category)
        
        queryset = queryset.select_related(
            'asset_category',
            'manager'
        ).prefetch_related(
            'assetsissuance_set',
            'assetsissuance_set__asset_assignee'
        ).order_by('-updated_date')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset_categories'] = AssetCategory.objects.all()
        context['is_employee'] = self.request.user.user_type == '3'
        
        # Add current filter values to context
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
            'category': self.request.GET.get('category', '')
        }
        
        return context

    
class AssetsDetailView(DetailView):
    model = Assets
    template_name = 'asset_app/asset_detail.html'
    context_object_name = 'asset'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        asset = self.object
        
        current_issuance = AssetsIssuance.objects.filter(
            asset=asset,
        ).select_related('asset_assignee').first()
        
        # Get historical issuances (inactive)
        historical_issuances = AssetAssignmentHistory.objects.filter(
            asset=asset,
        ).order_by('-date_assigned')

        context.update({
            'current_issuance': current_issuance,
            'historical_issuances': historical_issuances,
            'now': timezone.now() 
        })
        return context

class AssetCategoryCreateView(LoginRequiredMixin, CreateView):
    model = AssetCategory
    fields = ['category']
    template_name = 'asset_app/assetcategory_form.html'  
    success_url = reverse_lazy('asset_app:assets-list')

    # success_url = reverse_lazy('asset_app:assetcategory-list')

    def form_valid(self, form):
        form.instance.category = form.instance.category.lower()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_user'] = self.request.user
        return context

class AssetsCreateView(LoginRequiredMixin, CreateView):
    model = Assets
    fields = [
        'asset_category',
        'asset_name',
        'asset_brand', 
        'asset_serial_number',
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
    
    

class AssetUpdateView(LoginRequiredMixin, UpdateView):
    model = Assets
    form_class = AssetForm
    template_name = 'asset_app/asset_update.html'
    context_object_name = 'asset'

    def get_success_url(self):
        return reverse('asset_app:asset-update',kwargs={'pk' : self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request,'Asset Update Successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request,'There was an error Updating Asset.Please Check Form Fields!!')
        return super().form_invalid(form)


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



class MyAssetView(LoginRequiredMixin, ListView):
    template_name = 'asset_app/asset_assign.html'
    context_object_name = 'asset_issuances'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == '3':
            return AssetsIssuance.objects.filter(asset_assignee=user).select_related('asset').order_by('-date_issued')
        
        elif user.user_type == '2':
            return AssetsIssuance.objects.filter(
                asset__manager=user
            ).select_related('asset', 'asset_assignee').order_by('-date_issued')
        
        # elif user.user_type == '1':
        #     return AssetsIssuance.objects.all().select_related(
        #         'asset', 'asset_assignee', 'asset__manager'
        #     ).order_by('-date_issued')
        
        # return AssetsIssuance.objects.none()
        
   
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.user_type == '3':  
            context['total_assets'] = self.get_queryset().count()
            context['active_assets'] = self.get_queryset().filter(asset__is_asset_issued=True).count()
        else: 
            pass
            # context['total_issued'] = self.get_queryset().count()
            # context['active_assignments'] = self.get_queryset().filter(
            #     asset__is_asset_issued=True
            # ).count()
        
        return context

class AssetNotAssignListView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login_page")
    template_name = 'asset_app/not_assigned_asset_list.html'
    
    def handle_no_permission(self):
        messages.warning(self.request, "Please log in to access this page.")
        return redirect(self.login_url)
    
    def get(self, request):
        user = request.user
        not_assign_assets = Assets.objects.filter(is_asset_issued=False)
        if user.user_type in ['1','2']:
            return render(request, self.template_name, {
                'assets': not_assign_assets,
                'page_title': 'Not Assigned Asset List',
            })
        else:
            pending_requests = Notify_Manager.objects.filter(
                asset__in=not_assign_assets,
                manager__isnull=False,
                approved__isnull=True
            ).values_list('asset_id', flat=True)

            return render(request, self.template_name, {
                'assets': not_assign_assets,
                'pending_requests': list(pending_requests),
                'page_title': 'Not Assigned Asset List',
            })
        

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




