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
    path('<int:pk>/delete_table', views.delete_table, name='delete_table'),
    path('<int:pk>/add_column/', views.add_column, name='add_column'),
    path('<int:pk>/add_row/', views.add_row, name='add_row'),
    path('<int:table_pk>/delete_column/<int:column_pk>/', views.delete_column, name='delete_column'),
    path('<int:table_pk>/delete_row/<int:row_pk>/', views.delete_row, name='delete_row'),
]
