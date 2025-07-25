from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from main_app.EditSalaryView import EditSalaryView
from main_app.notification_badge import mark_notification_read
from . import ceo_views, manager_views, employee_views, views



urlpatterns = [
     path("", views.login_page, name='login_page'),
     path("get_attendance", views.get_attendance, name='get_attendance'),
     path("firebase-messaging-sw.js", views.showFirebaseJS, name='showFirebaseJS'),
     path("doLogin/", views.doLogin, name='user_login'),
     path("logout_user/", views.logout_user, name='user_logout'),
     path("admin/home/", ceo_views.admin_home, name='admin_home'),
     path("manager/add", ceo_views.add_manager, name='add_manager'),
     path("division/add", ceo_views.add_division, name='add_division'),
     path("send_employee_notification/", ceo_views.send_employee_notification,
          name='send_employee_notification'),
     path("send_manager_notification/", ceo_views.send_manager_notification,
          name='send_manager_notification'),
     path("admin_notify_employee", ceo_views.admin_notify_employee,
          name='admin_notify_employee'),
     path("admin_notify_manager", ceo_views.admin_notify_manager,
          name='admin_notify_manager'),
     path("admin_view_profile", ceo_views.admin_view_profile,
          name='admin_view_profile'),
          # In your admin URLs
     path('admin-todays-attendance/', ceo_views.admin_todays_attendance, name='admin_todays_attendance'),
     path("check_email_availability", ceo_views.check_email_availability,
          name="check_email_availability"),
     path("employee/view/feedback/", ceo_views.employee_feedback_message,
          name="employee_feedback_message",),
     path("manager/view/feedback/", ceo_views.manager_feedback_message,
          name="manager_feedback_message",),
     path("employee/view/leave/", ceo_views.view_employee_leave,
          name="view_employee_leave",),
     path("manager/view/leave/", ceo_views.view_manager_leave, name="view_manager_leave",),
     path("attendance/view/", ceo_views.admin_view_attendance,
          name="admin_view_attendance",),
     # path("attendance/fetch/", ceo_views.get_admin_attendance,name='get_admin_attendance'),
     path("employee/add/", ceo_views.add_employee, name='add_employee'),
     path("department/add/", ceo_views.add_department, name='add_department'),
     path("manager/manage/", ceo_views.manage_manager, name='manage_manager'),
     path("employee/manage/", ceo_views.manage_employee, name='manage_employee'),
     path("division/manage/", ceo_views.manage_division, name='manage_division'),
     path("department/manage/", ceo_views.manage_department, name='manage_department'),
     path("manager/edit/<int:manager_id>", ceo_views.edit_manager, name='edit_manager'),
     path("manager/delete/<int:manager_id>",
          ceo_views.delete_manager, name='delete_manager'),

     path('delete_asset_history_issues/', ceo_views.delete_asset_history_issues, name='delete_asset_history_issues'),
     path('send_bulk_employee_notification/', ceo_views.send_bulk_employee_notification, name='send_bulk_employee_notification'),
     path('send_selected_employee_notification/', ceo_views.send_selected_employee_notification, name='send_selected_employee_notification'),
     
     path('send_bulk_manager_notification/', ceo_views.send_bulk_manager_notification, name='send_bulk_manager_notification'),
     path('send_selected_manager_notification/', ceo_views.send_selected_manager_notification, name='send_selected_manager_notification'),
     path('view-employee/<int:employee_id>', ceo_views.view_employee, name='view_employee'),
     path('view-manager/<int:manager_id>', ceo_views.view_manager, name='view_manager'),
     path("manage/employees/", manager_views.manage_employee_by_manager, name='manage_employee_by_manager'),
     path("manager/add/employee/", manager_views.add_employee_by_manager, name='add_employee_by_manager'),
     path("manager/edit/employee/<int:employee_id>/", manager_views.edit_employee_by_manager, name='edit_employee_by_manager'),
     path("manager/delete/employee/<int:employee_id>/", manager_views.delete_employee_by_manager, name='delete_employee_by_manager'),

     path("manager_notify_employee/", manager_views.manager_notify_employee,
          name='manager_notify_employee'),
     
     path("manager_employee_notify/", manager_views.manager_send_employee_notification, name="manager_send_employee_notification"),

     path("division/delete/<int:division_id>",
          ceo_views.delete_division, name='delete_division'),

     path("department/delete/<int:department_id>",
          ceo_views.delete_department, name='delete_department'),

     path("employee/delete/<int:employee_id>",
          ceo_views.delete_employee, name='delete_employee'),
     path("employee/edit/<int:employee_id>",
          ceo_views.edit_employee, name='edit_employee'),
     path("division/edit/<int:division_id>",
          ceo_views.edit_division, name='edit_division'),
     path("department/edit/<int:department_id>",
          ceo_views.edit_department, name='edit_department'),
     path('generate_performance_report',ceo_views.generate_performance_report,name='generate_performance_report'),
     path('get_department_data' , ceo_views.get_department_data,name="get_department_data"),
     path('api/attendance/clock/', ceo_views.admin_view_attendance),

     path('admin_asset_issue_history/',ceo_views.admin_asset_issue_history,name="admin_asset_issue_history"),
     
     path('save_holidays/', ceo_views.save_holidays, name='save_holidays'),
     path('delete_holiday/', ceo_views.delete_holiday, name='delete_holiday'),
     path('get_holidays/', ceo_views.get_holidays, name='get_holidays'),
     path('clock-in-out/', views.clock_in_out, name='clock_in_out'),
     path('break/', views.break_action, name='break_action'),

     path('api/attendance/clock/', views.AttendanceActionView.as_view(), name='clock_in_out_api'),
     path("get_employee_attendance_by_admin/", ceo_views.get_manager_and_employee_attendance, name='get_manager_and_employee_attendance'),

     path("admin/view/notification/", ceo_views.admin_view_notification,name="admin_view_notification"),
     path('approve-manager-leave/<int:leave_id>/', ceo_views.approve_admin_leave_request, name='approve_manager_leave_request'),
     path('reject-manager-leave/<int:leave_id>/', ceo_views.reject_admin_leave_request, name='reject_manager_leave_request'),

     # Manager
     path("manager/home/", manager_views.manager_home, name='manager_home'),
     path("manager/apply/leave/", manager_views.manager_apply_leave,
          name='manager_apply_leave'),
     path("manager/feedback/", manager_views.manager_feedback, name='manager_feedback'),
     path("manager/view/profile/", manager_views.manager_view_profile,
          name='manager_view_profile'),
     path("admin/view/profile/", ceo_views.admin_view_profile,
          name='admin_view_profile'),
     path("manager/attendance/take/", manager_views.manager_take_attendance,
          name='manager_take_attendance'),
     path("manager/attendance/update/", manager_views.manager_update_attendance, name='manager_update_attendance'),
      
     path("manager/get_employees/", manager_views.get_employees, name='get_employees'),
     path("manager/get_managers/", manager_views.get_managers, name='get_managers'),
     path("manager/attendance/fetch/", manager_views.get_employee_attendance, name='get_employee_attendance'),
     path("manager/attendance/save/", manager_views.save_attendance, name='save_attendance'),
     path("manager/attendance/update-data/", manager_views.update_attendance,
     name='update_attendance'),
     path("manager/fcmtoken/", manager_views.manager_fcmtoken, name='manager_fcmtoken'),
     path("manager/view_asset/notification/", manager_views.manager_asset_view_notification,
          name="manager_asset_view_notification"),
     path("manager/view/notification/", manager_views.manager_view_notification,
          name="manager_view_notification"),

     path("manager/salary/add/", manager_views.manager_add_salary, name='manager_add_salary'),
     path("manager/salary/edit/", EditSalaryView.as_view(),
          name='edit_employee_salary'),
     path('manager/salary/fetch/', manager_views.fetch_employee_salary,
          name='fetch_employee_salary'),
     path('manager/asset-approve/<int:notification_id>/', manager_views.approve_assest_request,
          name='approve_assest_request'),
     path('manager/asset-reject/<int:notification_id>/', manager_views.reject_assest_request,
          name='reject_assest_request'),
     path('manager/leave-approve/<int:leave_id>/', manager_views.approve_leave_request,
          name='approve_leave_request'),
     path('manager/leave-reject/<int:leave_id>/', manager_views.reject_leave_request,
          name='reject_leave_request'),
     path('notification/read/', mark_notification_read, name='mark_notification_read'),
     path('manager-todays-attendance/', manager_views.manager_todays_attendance, name='manager_todays_attendance'),

     path('get_asset_categories/', manager_views.get_asset_categories, name='get_asset_categories'),
     path('get_available_assets/', manager_views.get_available_assets, name='get_available_assets'),
     path('get_assigned_assets/', manager_views.get_assigned_assets, name='get_assigned_assets'),
     path('assign_assets/', manager_views.assign_assets, name='assign_assets'),
     path('remove_asset_assignment/', manager_views.remove_asset_assignment, name='remove_asset_assignment'),
     path('remove_selected_asset_assignment/', manager_views.remove_selected_asset_assignment, name='remove_selected_asset_assignment'),
     path('remove_all_asset_assignment/', manager_views.remove_all_asset_assignment, name='remove_all_asset_assignment'),
     
     path('resolve_asset_issue/<int:asset_issu_id>/', manager_views.resolve_asset_issue, name='resolve_asset_issue'),

     path('send_selected_employee_notification_by_manager', manager_views.send_selected_employee_notification_by_manager, name='send_selected_employee_notification_by_manager'),
     path('send_bulk_employee_notification_by_manager', manager_views.send_bulk_employee_notification_by_manager, name='send_bulk_employee_notification_by_manager'),
     path("manager/employee/view/feedback/", manager_views.manager_view_by_employee_feedback_message,name="manager_view_by_employee_feedback_message",),
     path("manager/employee/view/leave/", manager_views.manager_view_by_employee_leave,name="manager_view_by_employee_leave",),
     path('manager-leave-balance/', manager_views.manager_leave_balance, name='manager_leave_balance'),

     path("view_employee_by_manager/<int:employee_id>/", manager_views.view_employee_by_manager,name="view_employee_by_manager",),

     # Employee
     path("employee/home/", employee_views.employee_home, name='employee_home'),
     path("employee/view/attendance/", employee_views.employee_view_attendance,name='employee_view_attendance'),
     path("employee/apply/leave/", employee_views.employee_apply_leave,
          name='employee_apply_leave'),
     path("employee/feedback/", employee_views.employee_feedback,
          name='employee_feedback'),
     path("employee/view/profile/", employee_views.employee_view_profile,
          name='employee_view_profile'),
     path("employee/fcmtoken/", employee_views.employee_fcmtoken,
          name='employee_fcmtoken'),
     path("employee/view/notification/", employee_views.employee_view_notification,
          name="employee_view_notification"),
     path('employee/view/salary/', employee_views.employee_view_salary,
          name='employee_view_salary'),
     path('employee/view/requests-status/', employee_views.employee_requests,
          name='employee_requests'),  
     path('employee/daily_schedule/', employee_views.daily_schedule,
          name='daily_schedule'),  
     path('employee/todays_update', employee_views.todays_update,name='todays_update'),  
     path('employee/view_all_schedules', employee_views.view_all_schedules,name='view_all_schedules'),  
     path('employee/others_schedule', employee_views.others_schedule,name='others_schedule'),  


     path('early-clock-out-request/', views.early_clock_out_request, name='early_clock_out_request'),
     path('check-early-clock-out-status/', views.check_early_clock_out_status, name='check_early_clock_out_status'),
     path('approve-early-clock-out/<int:request_id>/', views.approve_early_clock_out, name='approve_early_clock_out'),
     path('deny-early-clock-out/<int:request_id>/', views.deny_early_clock_out, name='deny_early_clock_out'),
     path('dearly_clock_out_request_page/', employee_views.early_clock_out_request_page, name='early_clock_out_request_page'),
     path('leave-balance/', employee_views.leave_balance, name='leave_balance'),


     path('all_employees_schedules/', views.all_employees_schedules, name='all_employees_schedules'),

     path('check-notifications/', views.check_new_notification, name='check_new_notification'),
    

    
]
