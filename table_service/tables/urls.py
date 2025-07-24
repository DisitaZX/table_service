from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', views.table_list, name='table_list'),
    path('create/', views.create_table, name='create_table'),
    path('<int:pk>/', views.table_detail, name='table_detail'),
    path('<int:pk>/edit_table', views.edit_table, name='edit_table'),
    path('<int:pk>/delete_table', views.delete_table, name='delete_table'),
    path('<int:pk>/add_column/', views.add_column, name='add_column'),
    path('<int:pk>/<int:column_pk>/edit_column/', views.edit_column, name='edit_column'),
    path('<int:pk>/add_row/', views.add_row, name='add_row'),
    path('<int:table_pk>/delete_column/<int:column_pk>/', views.delete_column, name='delete_column'),
    path('<int:table_pk>/delete_row/<int:row_pk>/', views.delete_row, name='delete_row'),
    path('<int:table_pk>/edit_row/<int:row_pk>/', views.edit_row, name='edit_row'),
    path('<int:table_pk>/mass_edit_row/', views.mass_edit_row, name='mass_edit_row'),
    path('<int:table_pk>/mass_delete_row/', views.mass_delete_row, name='mass_delete_row'),
    path('shared/', views.shared_tables_list, name='shared_tables_list'),
    path('shared/<str:share_token>/', views.shared_table_view, name='shared_table_view'),
    path('shared/<str:share_token>/revoke_redact/<int:id_filial>', views.revoke_redact_rows, name='revoke_redact_rows'),
    path('<int:table_pk>/manage_table_permissions/', views.manage_table_permissions, name='manage_table_permissions'),
    path('api/unlock_row/<int:row_pk>/', views.unlock_row_api, name='unlock_row_api'),
    path('admins/', views.manage_admins, name='manage_admins'),
    path('<int:table_pk>/import_new_rows/', views.import_new_rows, name='import_new_rows'),
    path('<int:table_pk>/export/', views.export_table, name='export_table'),
    path('import_table/', views.import_table, name='import_table'),
    path('media/files/<str:name_file>', views.download_file, name='download_file'),
    path('ajax/get-user-filials/', views.get_user_filials, name='get_user_filials'),
]
