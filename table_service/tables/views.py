import datetime
import os
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Value, TextField, Subquery, OuterRef, Q
from django.db.models.fields.files import FieldFile
from django.db.models.functions import Concat
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, FileResponse
from django.urls import reverse
from django.template.loader import render_to_string
from django_tables2.export import TableExport
from .models import Table, Column, Row, Cell, Filial, Employee, TablePermission, \
    TableFilialPermission, Admin, UserFilial
from .forms import TableForm, ColumnForm, RowEditForm, AddRowForm, PermissionUserForm, PermissionFilialForm, \
    TablePermissionForm, TableFilialPermissionForm, PermissionUserFilialForm, UserFilialForm, ColumnEditForm
from .service import unlock_row, lock_row
from django.contrib import messages
from django_tables2 import RequestConfig
from .tables import DynamicTable, ExportTable
from django.views.decorators.http import require_POST
from django.conf import settings


def get_user_filials(request):
    """AJAX view для получения филиалов пользователя"""
    user_id = request.GET.get('user_id')
    table_id = request.GET.get('table_id')

    if not user_id or not table_id:
        return JsonResponse({'filials': []})

    try:
        user = User.objects.get(id=user_id)
        table = Table.objects.get(id=table_id)

        # Основной филиал пользователя
        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)

        # Дополнительные филиалы пользователя для этой таблицы
        additional_filials = UserFilial.objects.filter(
            user=user,
            table=table
        ).select_related('filial')

        # Собираем все филиалы
        filials = [{
            'id': main_filial.id,
            'name': main_filial.name
        }]

        for user_filial in additional_filials:
            filials.append({
                'id': user_filial.filial.id,
                'name': user_filial.filial.name
            })

        return JsonResponse({'filials': filials})

    except (User.DoesNotExist, Table.DoesNotExist, Employee.DoesNotExist, Filial.DoesNotExist):
        return JsonResponse({'filials': []})


def save_row_data(row, form, columns):
    """Сохраняет данные строки из формы"""
    for column in columns:
        field_name = f'col_{column.id}'
        value = form.cleaned_data[field_name]

        # Для файловых полей
        if column.data_type == Column.ColumnType.FILE:
            clear_flag = form.data.get(f'{field_name}-clear', False)
            cell, created = Cell.objects.get_or_create(
                row=row,
                column=column,
                defaults={'file_value': None}
            )
            # Если передано новое значение файла или передан флажок удаления файла
            if clear_flag or (value and not isinstance(value, FieldFile)):
                if cell.file_value:
                    try:
                        default_storage.delete(cell.file_value.name)
                    except Exception as e:
                        print(f"Ошибка удаления файла {cell.file_value.name}: {e}")

                # Если загружен новый файл — сохраняем его
            if value and not isinstance(value, FieldFile):
                cell.file_value.save(value.name, value)
                cell.save()
                # Если стоит галочка удаления И НЕМ нового файла — очищаем поле
            elif clear_flag:
                cell.file_value = None
                cell.save()

        # Для не-файловых полей
        else:
            Cell.objects.update_or_create(
                row=row,
                column=column,
                defaults={'value': value}
            )


@login_required
def table_list(request):
    if Admin.objects.filter(user=request.user).exists():
        tables = Table.objects.all()
    else:
        tables = Table.objects.filter(owner=request.user)
    return render(request, 'tables/table_list.html', {'tables': tables})


@login_required
def create_table(request):
    if request.method == 'POST':
        form = TableForm(request.POST)
        if form.is_valid():
            table = form.save(commit=False)
            table.owner = request.user
            table.created_at = datetime.datetime.now()
            table.save()

            return redirect('table_detail', pk=table.pk)
    else:
        form = TableForm()
    return render(request, 'tables/create_table.html', {'form': form})


@login_required
def delete_table(request, pk):
    table = get_object_or_404(Table, pk=pk)

    # Проверка прав
    if not (table.owner == request.user or table.is_admin(request.user)):
        return HttpResponseForbidden("Вы не можете удалять таблицы")

    table.delete()

    messages.success(request, f'Таблица "{table.title}" успешно удалена')
    return redirect('table_list')


@login_required
def add_column(request, pk):
    table = get_object_or_404(Table, pk=pk)

    # Проверка прав (только владелец может добавлять колонки)
    if not (table.owner == request.user or table.is_admin(request.user)):
        return HttpResponseForbidden("Вы не можете добавлять колонки в эту таблицу")

    if request.method == 'POST':
        form = ColumnForm(request.POST, table=table)
        if form.is_valid():
            with transaction.atomic():
                column = form.save(commit=False)
                column.table = table
                column.order = table.columns.count()
                column.save()

                messages.success(request, f'Колонка "{column.name}" успешно добавлена')
                return redirect('table_detail', pk=table.pk)
    else:
        form = ColumnForm(table=table)
    return render(request, 'tables/add_column/add_column.html', {'form': form, 'table': table})


@login_required
def edit_column(request, pk, column_pk):
    table = get_object_or_404(Table, pk=pk)
    column = get_object_or_404(Column, pk=column_pk, table=table)
    # Проверка прав (только владелец может редактировать колонки)
    if not (table.owner == request.user or table.is_admin(request.user)):
        return HttpResponseForbidden("Вы не можете добавлять колонки в эту таблицу")

    if request.method == 'POST':
        form = ColumnEditForm(request.POST, instance=column, table=table)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                messages.success(request, f'Колонка успешно обновлена')
                return redirect('table_detail', pk=table.pk)
    else:
        form = ColumnEditForm(instance=column, table=table)
    return render(request, 'tables/add_column/edit_column.html', {'form': form, 'table': table, 'column': column})


@login_required
def manage_admins(request):
    if request.method == 'POST':
        with transaction.atomic():
            if 'add_admin' in request.POST:
                with transaction.atomic():
                    user_id = request.POST.get('new_admin')
                    if user_id:
                        user = get_object_or_404(User, pk=user_id)
                        Admin.objects.get_or_create(user=user)
                        messages.success(request, f'{user.username} добавлен как администратор')

            if 'remove_admin' in request.POST:
                with transaction.atomic():
                    admin_id = request.POST.get('admin_id')
                    if admin_id:
                        Admin.objects.filter(pk=admin_id).delete()
                        messages.success(request, 'Администратор удален')

        return redirect('manage_admins')

    current_admins = Admin.objects.all()
    available_users = User.objects.all()

    return render(request, 'tables/manage_admins.html', {
        'current_admins': current_admins,
        'available_users': available_users,
        'is_admin': Admin.objects.filter(user=request.user)
    })


@login_required
def manage_table_permissions(request, table_pk):
    table = get_object_or_404(Table, pk=table_pk)

    if not (table.owner == request.user or table.is_admin(request.user)):
        return HttpResponseForbidden("Только владелец таблицы или администратор может редактировать права на таблицу")

    if request.method == 'POST':
        with transaction.atomic():
            if 'update_user' in request.POST:
                user_id, filial_id = request.POST.get('update_user').split('|')
                perm = table.permissions.get(table=table, user_id=user_id, filial_id=filial_id)
                field_name = f'user_{perm.user.id}-permission_type'
                if field_name in request.POST:
                    perm.permission_type = request.POST[field_name]
                    perm.save()
                messages.success(request, 'Права пользователей обновлены')

            elif 'remove_user' in request.POST:
                user_id, filial_id = request.POST.get('user_id').split('|')
                if user_id:
                    table.permissions.filter(table=table, user_id=user_id, filial_id=filial_id).delete()
                    messages.success(request, 'Права пользователя удалены')

            elif 'add_user' in request.POST:
                user_id = request.POST.get('user')
                filial_id = request.POST.get('filial')
                permission_type = request.POST.get('permission_type')
                if user_id and permission_type:
                    TablePermission.objects.update_or_create(
                        table=table,
                        user_id=user_id,
                        filial_id=filial_id,
                        defaults={
                            'permission_type': permission_type
                        }
                    )
                    messages.success(request, 'Права пользователя добавлены')

            elif 'update_filial' in request.POST:
                filial_id = request.POST.get('update_filial')
                perm = table.filial_permissions.get(table=table, filial_id=filial_id)
                field_name = f'filial_{perm.filial.id}-permission_type'
                if field_name in request.POST:
                    perm.permission_type = request.POST[field_name]
                    perm.save()
                messages.success(request, 'Права филиала обновлены')

            elif 'remove_filial' in request.POST:
                filial_id = request.POST.get('filial_id')
                if filial_id:
                    table.filial_permissions.filter(filial_id=filial_id).delete()

                    messages.success(request, 'Права филиала удалены')

            elif 'add_filial' in request.POST:
                filial_id = request.POST.get('filial')
                permission_type = request.POST.get('permission_type')
                if filial_id and permission_type:
                    TableFilialPermission.objects.update_or_create(
                        table=table,
                        filial_id=filial_id,
                        defaults={'permission_type': permission_type}
                    )

                    messages.success(request, 'Права филиала добавлены')

            elif 'remove_user_filial' in request.POST:
                user_id, filial_id = request.POST.get('user_filial_id').split('|')
                if user_id and filial_id:
                    UserFilial.objects.filter(table=table, user_id=user_id, filial_id=filial_id).delete()
                    table.permissions.filter(table=table, user_id=user_id, filial_id=filial_id).delete()
                    messages.success(request, 'Права пользователя удалены')

            elif 'add_user_filial' in request.POST:
                user_id = request.POST.get('user')
                filial_id = request.POST.get('filial')
                if user_id and filial_id:
                    UserFilial.objects.update_or_create(
                        table=table,
                        user_id=user_id,
                        filial_id=filial_id,
                    )

                    messages.success(request, 'Дополнительные права филиала добавлены')

        return redirect('manage_table_permissions', table_pk=table.pk)

    # Получаем текущие разрешения пользователей для таблицы
    permissions = []
    for perm in table.permissions.all():
        perm.form = TablePermissionForm(initial={
            'permission_type': perm.permission_type,
            'filial': perm.filial,
        }, prefix=f'user_{perm.user.id}')
        permissions.append(perm)

    # Получаем текущие разрешения филиалов для таблицы
    filial_permissions = []
    for perm in table.filial_permissions.all():
        perm.form = TableFilialPermissionForm(initial={
            'permission_type': perm.permission_type
        }, prefix=f'filial_{perm.filial.id}')
        filial_permissions.append(perm)

    userfilial_permissions = []
    for perm in UserFilial.objects.filter(table=table):
        perm.form = UserFilialForm(initial={
            'user': perm.user,
            'filial': perm.filial
        })
        userfilial_permissions.append(perm)

    return render(request, 'tables/manage_table_permissions.html', {
        'table': table,
        'permissions': permissions,
        'filial_permissions': filial_permissions,
        'userfilial_permissions': userfilial_permissions,
        'user_form': PermissionUserForm(table=table),
        'filial_form': PermissionFilialForm(table=table),
        'user_filial_form': PermissionUserFilialForm(table=table)
    })


@login_required
def revoke_redact_rows(request, share_token, id_filial):
    table = get_object_or_404(Table, share_token=share_token)

    if not table.has_view_permission(request.user):
        return HttpResponseForbidden("У вас нет прав на завершение редактирования этой таблицы")

    try:
        with transaction.atomic():
            if id_filial:
                filial = Filial.objects.get(id=id_filial)

                TableFilialPermission.objects.update_or_create(
                    table=table,
                    filial=filial,
                    defaults={
                        'permission_type': 'RNN'
                    }
                )
                TablePermission.objects.update_or_create(
                    table=table,
                    filial=filial,
                    defaults={
                        'permission_type': 'RNN'
                    }
                )

                messages.success(request, f'Права редактирования для филиала {filial.name} сняты со всех строк')
            else:
                TableFilialPermission.objects.filter(table=table).update(permission_type='RNN')
                TablePermission.objects.filter(table=table).update(permission_type='RNN')

                messages.success(request, f'Права редактирования для всех пользователей и филиалов сняты со всех строк')

        if table.owner == request.user or table.is_admin(request.user):
            return redirect('table_detail', pk=table.pk)
        return redirect('shared_table_view', share_token=table.share_token)

    except Exception as e:
        messages.error(request, f'Ошибка при снятии прав: {str(e)}')
        if table.owner == request.user or table.is_admin(request.user):
            return redirect('table_detail', pk=table.pk)
        return redirect('shared_table_view', share_token=table.share_token)


@login_required
def delete_column(request, table_pk, column_pk):
    table = get_object_or_404(Table, pk=table_pk)
    column = get_object_or_404(Column, pk=column_pk, table=table)

    # Проверка прав
    if not (table.owner == request.user or table.is_admin(request.user)):
        return HttpResponseForbidden("Вы не можете удалять колонки из этой таблицы")

    Cell.objects.filter(column=column).delete()
    column.delete()

    messages.success(request, f'Колонка "{column.name}" успешно удалена')
    return redirect('table_detail', pk=table.pk)


@login_required
def delete_row(request, table_pk, row_pk):
    table = get_object_or_404(Table, pk=table_pk)
    row = get_object_or_404(Row, pk=row_pk, table=table)

    # Проверка прав
    if not row.has_delete_permission(request.user):
        return JsonResponse({'status': 'error', 'message': 'Нет прав на удаление'}, status=403)

    row.delete()
    messages.success(request, 'Строка успешно удалена')

    if request.user == table.owner:
        return JsonResponse({'status': 'success', 'redirect_url': reverse('table_detail', kwargs={'pk': table.pk})})
    else:
        return JsonResponse({'status': 'success', 'redirect_url': reverse('shared_table_view',
                                                                          kwargs={'share_token': table.share_token})})


@require_POST
@login_required
def unlock_row_api(request, row_pk):
    row = get_object_or_404(Row, pk=row_pk)
    if unlock_row(row, request.user):
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def edit_row(request, table_pk, row_pk):
    table = get_object_or_404(Table, pk=table_pk)
    row = get_object_or_404(Row, pk=row_pk, table=table)
    if not row.has_edit_permission(request.user):
        return JsonResponse({'status': 'error', 'message': 'Нет прав на редактирование'}, status=403)

    columns = table.columns.all()

    if request.method == 'POST':
        form = RowEditForm(request.POST, request.FILES, row=row, columns=columns)
        if form.is_valid():
            # Снимаем блокировку после успешного редактирования
            unlock_row(row, request.user)
            save_row_data(row, form, columns)
            row.updated_by = request.user
            row.last_date = datetime.datetime.now()
            row.save()
            messages.success(request, 'Строка успешно отредактирована!')
            return JsonResponse({'status': 'success'})
        errors = [error_list[0] for field, error_list in form.errors.items()]
        return JsonResponse({'status': 'error', 'message': errors[0]}, status=400)

    lock, lock_user = lock_row(row, request.user)
    if not lock:
        return JsonResponse({
            'status': 'error',
            'message': f'Строка сейчас редактируется другим пользователем: {lock_user}'
        }, status=423)  # 423 - Locked

    # GET запрос - возвращаем форму
    form = RowEditForm(row=row, columns=columns)
    html = render_to_string('tables/row_edit_form/row_edit_form.html', {
        'form': form,
        'table': table,
        'row': row
    }, request=request)
    return JsonResponse({'status': 'success', 'html': html})


@login_required
def add_row(request, pk):
    table = get_object_or_404(Table, pk=pk)

    if not table.has_add_permission(request.user):
        return JsonResponse({'status': 'error', 'message': "Вы не можете добавлять строки в эту таблицу"}, status=403)

    columns = table.columns.all()

    available_filials = get_available_filials_for_adding(request.user, table)

    if request.method == 'POST':
        form = AddRowForm(request.POST, request.FILES, table=table, columns=columns, user=request.user,
                          available_filials=available_filials)
        if form.is_valid():
            selected_filial = form.cleaned_data['filial']
            # Создаем новую строку
            row = Row.objects.create(
                table=table,
                order=table.rows.count(),  # Порядковый номер новой строки
                filial=selected_filial,
                created_by=request.user,
                updated_by=request.user,
                last_date=datetime.datetime.now()
            )

            # Заполняем ячейки данными из формы
            for column in columns:
                field_name = f'col_{column.id}'
                value = form.cleaned_data.get(field_name)

                Cell.objects.create(
                    row=row,
                    column=column,
                    value=value
                )

            messages.success(request, 'Новая строка успешно добавлена')
            return JsonResponse({'status': 'success'})
        errors = [error_list[0] for field, error_list in form.errors.items()]
        return JsonResponse({'status': 'error', 'message': errors[0]}, status=400)

    # GET запрос - возвращаем форму
    form = AddRowForm(table=table, user=request.user, columns=columns, available_filials=available_filials)
    html = render_to_string('tables/add_row/add_row.html', {
        'form': form,
        'table': table  # Передаем сам объект таблицы
    }, request=request)
    return JsonResponse({'status': 'success', 'html': html})


@login_required
def shared_tables_list(request):
    # Получаем все таблицы, к которым у пользователя есть доступ
    shared_tables = Table.get_shared_tables(request.user)

    # Добавляем информацию о правах для каждой таблицы
    tables_with_access = []
    for table in shared_tables:
        if table.owner == request.user:
            is_owner = True
        else:
            is_owner = False

        can_edit = is_owner or TablePermission.objects.filter(
            table=table,
            user=request.user,
            permission_type__in=['RWD', 'RWN']
        ).exists() or TableFilialPermission.objects.filter(
            table=table,
            filial=request.user.profile.employee.id_filial,
            permission_type__in=['RWD', 'RWN']
        ).exists()

        can_delete = is_owner or TablePermission.objects.filter(
            table=table,
            user=request.user,
            permission_type__in=['RWD']
        ).exists() or TableFilialPermission.objects.filter(
            table=table,
            filial=request.user.profile.employee.id_filial,
            permission_type__in=['RWD']
        ).exists()

        tables_with_access.append({
            'table': table,
            'is_owner': is_owner,
            'can_edit': can_edit,
            'can_delete': can_delete,
            'shared_by': table.owner.username
        })

    return render(request, 'tables/shared_tables_list.html', {
        'tables': tables_with_access
    })


@login_required
def table_detail(request, pk):
    table_obj = get_object_or_404(Table, pk=pk)
    # Проверка прав доступа
    if not (table_obj.owner == request.user or table_obj.is_admin(request.user)):
        return HttpResponseForbidden("У вас нет прав на доступ к этой таблице")

    queryset = table_obj.rows.all().prefetch_related('cells', 'cells__column')
    columns = table_obj.columns.all()

    queryset, search_query = filter_func(queryset, columns, request)

    # Добавляем аннотации для каждого столбца
    queryset = sort_func(queryset, columns)

    table = DynamicTable(data=queryset, table_obj=table_obj, columns=columns, request=request)
    RequestConfig(request).configure(table)

    filials = Filial.objects.filter(
        Q(tablefilialpermission__table=table_obj,
          tablefilialpermission__permission_type__in=['RWD', 'RWN']) |
        Q(tablepermission__table=table_obj,
          tablepermission__permission_type__in=['RWD', 'RWN'])
    ).distinct()

    return render(request, 'tables/table_detail.html', {
        'table_obj': table_obj,
        'table': table,
        'filials': filials,
        'is_admin': table_obj.is_admin(request.user),
        'search_query': search_query
    })


@login_required()
def shared_table_view(request, share_token):
    table = get_object_or_404(Table, share_token=share_token)

    if not table.has_view_permission(request.user):
        return HttpResponseForbidden("У вас нет прав на просмотр этой таблицы")

    # Получаем строки, которые пользователь может видеть
    rows = Row.get_visible_rows(request.user, table)
    columns = table.columns.all()

    rows, search_query = filter_func(rows, columns, request)

    queryset = sort_func(rows, columns)
    table_view = DynamicTable(data=queryset, table_obj=table, columns=columns, request=request)
    RequestConfig(request).configure(table_view)

    filials = check_filial_rights(request.user, table)

    return render(request, 'tables/shared_table.html', {
        'table_obj': table,
        'table': table_view,
        'filials': filials,
        'is_owner': table.owner == request.user,
        'is_admin': table.is_admin(request.user),
        'is_add_permission': True if filials else False,
        'search_query': search_query
    })


@login_required
def export_table(request, table_pk):
    table_obj = get_object_or_404(Table, pk=table_pk)
    # Проверка прав доступа
    if not (table_obj.owner == request.user or table_obj.is_admin(request.user)):
        return HttpResponseForbidden("Вы не можете скачать таблицу")

    queryset = table_obj.rows.all().prefetch_related('cells', 'cells__column')

    table = ExportTable(data=queryset, table_obj=table_obj, request=request)

    RequestConfig(request).configure(table)

    export_format = request.GET.get("_export", None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response(f"table.{export_format}")

    return render(request, "tables/export/export_table.html", {
        "table": table
    })


@login_required
def download_file(request, name_file):
    full_path = os.path.join(settings.MEDIA_ROOT + '/files', name_file)
    if not os.path.exists(full_path):
        return HttpResponseForbidden("Файл не найден")

    response = FileResponse(open(full_path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(name_file)}"'
    return response


def check_filial_rights(user, table):
    """Возвращает филиалы, где пользователь имеет права 'RWD' 'RWN'"""
    # Получаем все филиалы пользователя (основной + дополнительные)
    filials = Filial.objects.filter(id=user.profile.employee.id_filial)
    additional_filials = UserFilial.objects.filter(user=user, table=table)
    for q in additional_filials:
        filials |= Filial.objects.filter(id=q.filial.id)

    # Создаем список ID филиалов, которые нужно исключить
    exclude_ids = []

    for f in filials:
        has_filial_permission = TableFilialPermission.objects.filter(
            filial=f,
            table=table,
            permission_type__in=['RWD', 'RWN']
        ).exists()

        has_user_deny = TablePermission.objects.filter(
            user=user,
            filial=f,
            permission_type__in=['RNN', 'NNN']
        ).exists()

        has_user_permission = TablePermission.objects.filter(
            user=user,
            filial=f,
            permission_type__in=['RWD', 'RWN']
        ).exists()

        # Если нет ни одного из разрешающих условий, добавляем в исключения
        if not ((has_filial_permission and not has_user_deny) or has_user_permission):
            exclude_ids.append(f.id)

    # Исключаем филиалы без прав доступа
    if exclude_ids:
        filials = filials.exclude(id__in=exclude_ids)

    return filials.distinct()


def get_available_filials_for_adding(user, table):
    """Возвращает филиалы, где пользователь имеет права на добавление строк"""
    # Получаем все доступные филиалы с проверкой прав
    if table.is_admin(user):
        return Filial.objects.all()
    if table.owner == user:
        return Filial.objects.all()

    available_filials = check_filial_rights(user, table)

    # Дополнительно фильтруем только те, где есть права на добавление (RWD/RWN)
    adding_filials = available_filials.filter(
        Q(
            tablefilialpermission__table=table,
            tablefilialpermission__permission_type__in=['RWD', 'RWN']
        ) | Q(
            tablepermission__user=user,
            tablepermission__permission_type__in=['RWD', 'RWN']
        )
    ).distinct()

    return adding_filials


def filter_func(queryset, columns, request):
    search_query = request.GET.get('q', '')
    if search_query:
        # Создаем условие для поиска по всем колонкам
        column_conditions = Q()
        for column in columns:
            column_conditions |= Q(cells__column=column, cells__text_value__icontains=search_query)
            column_conditions |= Q(cells__column=column, cells__url_value__icontains=search_query)
            column_conditions |= Q(cells__column=column, cells__email_value__icontains=search_query)
            if column.data_type == Column.ColumnType.INTEGER:
                try:
                    int_value = int(search_query)
                    column_conditions |= Q(cells__column=column, cells__integer_value=int_value)
                except ValueError:
                    pass
            elif column.data_type == Column.ColumnType.FLOAT:
                try:
                    float_value = float(search_query)
                    column_conditions |= Q(cells__column=column,
                                           cells__float_value__gte=float_value - 0.001,
                                           cells__float_value__lte=float_value + 0.001)
                except ValueError:
                    pass
            elif column.data_type == Column.ColumnType.BOOLEAN:
                # Поиск по булевым значениям (true/false, да/нет и т.д.)
                bool_value = None
                if search_query.lower() in ['true', 'да', 'yes', 'истина']:
                    bool_value = True
                elif search_query.lower() in ['false', 'нет', 'no', 'ложь']:
                    bool_value = False

                if bool_value is not None:
                    column_conditions |= Q(cells__column=column, cells__boolean_value=bool_value)
            elif column.data_type == Column.ColumnType.DATE:
                try:
                    # Пробуем разные форматы дат
                    date_formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%m/%d/%Y']
                    parsed_date = None
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.datetime.strptime(search_query, fmt).date()
                            break
                        except ValueError:
                            continue

                    if parsed_date:
                        column_conditions |= Q(cells__column=column, cells__date_value=parsed_date)
                except ValueError:
                    pass

        filter_filial_ids = Filial.objects.filter(
            Q(name__icontains=search_query) |
            Q(long_name__icontains=search_query) |
            Q(short_name__icontains=search_query)
        ).values_list('id', flat=True)

        queryset = queryset.filter(
            column_conditions |
            Q(created_by__profile__employee__firstname__icontains=search_query) |
            Q(created_by__profile__employee__secondname__icontains=search_query) |
            Q(created_by__profile__employee__lastname__icontains=search_query) |
            Q(filial__id__in=filter_filial_ids) |
            Q(updated_by__profile__employee__firstname__icontains=search_query) |
            Q(updated_by__profile__employee__secondname__icontains=search_query) |
            Q(updated_by__profile__employee__lastname__icontains=search_query)
        ).distinct()

        return queryset, search_query

    filter_filial = request.GET.get('filter_is_filial', '')
    filter_user = request.GET.get('filter_is_user', '')
    filter_update_user = request.GET.get('filter_is_update_user', '')
    filter_update_time_start = request.GET.get('filter_is_update_time_start', '')
    filter_update_time_end = request.GET.get('filter_is_update_time_end', '')
    if filter_filial:
        queryset = queryset.filter(
            Q(filial__name__icontains=filter_filial)
        ).distinct()
    if filter_user:
        queryset = queryset.filter(
            Q(created_by__profile__employee__firstname__icontains=filter_user) |
            Q(created_by__profile__employee__secondname__icontains=filter_user) |
            Q(created_by__profile__employee__lastname__icontains=filter_user)
        ).distinct()
    if filter_update_user:
        queryset = queryset.filter(
            Q(updated_by__profile__employee__firstname__icontains=filter_update_user) |
            Q(updated_by__profile__employee__secondname__icontains=filter_update_user) |
            Q(updated_by__profile__employee__lastname__icontains=filter_update_user)
        ).distinct()
    if filter_update_time_start:
        try:
            queryset = queryset.filter(
                Q(last_date__gte=filter_update_time_start)
            ).distinct()
        except ValueError:
            pass
        if filter_update_time_end:
            try:
                queryset = queryset.filter(
                    Q(last_date__lte=filter_update_time_end)
                ).distinct()
            except ValueError:
                pass

    # Фильтрация по колонкам
    for column in columns:
        filter_value = request.GET.get(f'filter_{column.id}')

        if column.data_type == Column.ColumnType.CHOICE and column.choices and filter_value:
            # Фильтр для выбора из списка
            queryset = queryset.filter(
                cells__column=column,
                cells__choice_value=filter_value
            )
        elif column.data_type == Column.ColumnType.BOOLEAN and filter_value:
            # Фильтр для булевых значений
            bool_value = filter_value.lower() == 'true'
            queryset = queryset.filter(
                cells__column=column,
                cells__boolean_value=bool_value
            )
        elif column.data_type in [Column.ColumnType.INTEGER, Column.ColumnType.POSITIVE_INTEGER]:
            # Фильтр для целых чисел
            min_value = request.GET.get(f'filter_{column.id}_min')
            max_value = request.GET.get(f'filter_{column.id}_max')

            if min_value:
                try:
                    queryset = queryset.filter(
                        cells__column=column,
                        cells__integer_value__gte=int(min_value)
                    )
                except ValueError:
                    pass
            if max_value:
                try:
                    queryset = queryset.filter(
                        cells__column=column,
                        cells__integer_value__lte=int(max_value)
                    )
                except ValueError:
                    pass
        elif column.data_type == Column.ColumnType.FLOAT:
            # Фильтр для чисел с плавающей точкой
            min_value = request.GET.get(f'filter_{column.id}_min')
            max_value = request.GET.get(f'filter_{column.id}_max')

            if min_value:
                try:
                    queryset = queryset.filter(
                        cells__column=column,
                        cells__float_value__gte=float(min_value)
                    )
                except ValueError:
                    pass
            if max_value:
                try:
                    queryset = queryset.filter(
                        cells__column=column,
                        cells__float_value__lte=float(max_value)
                    )
                except ValueError:
                    pass
        elif column.data_type == Column.ColumnType.DATE:
            # Фильтр для дат
            start_date = request.GET.get(f'filter_{column.id}_start')
            end_date = request.GET.get(f'filter_{column.id}_end')
            print(start_date)
            print(end_date)
            if start_date:
                try:
                    start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(
                        cells__column=column,
                        cells__date_value__gte=start_date
                    )
                except ValueError:
                    pass
            if end_date:
                try:
                    end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(
                        cells__column=column,
                        cells__date_value__lte=end_date
                    )
                except ValueError:
                    pass
        elif column.data_type == Column.ColumnType.TEXT and filter_value:
            queryset = queryset.filter(
                cells__column=column,
                cells__text_value__icontains=filter_value
            )
        elif column.data_type == Column.ColumnType.URL and filter_value:
            queryset = queryset.filter(
                cells__column=column,
                cells__url_value__icontains=filter_value
            )
        elif column.data_type == Column.ColumnType.EMAIL and filter_value:
            queryset = queryset.filter(
                cells__column=column,
                cells__email_value__icontains=filter_value
            )

    return queryset, search_query


def sort_func(queryset, columns):
    queryset = queryset.annotate(
        user_full_name=Concat(
            F('created_by__profile__employee__secondname'),
            Value(' '),
            F('created_by__profile__employee__firstname'),
            Value(' '),
            F('created_by__profile__employee__lastname'),
            output_field=TextField()
        ),
    )

    queryset = queryset.annotate(
        filial_name=Subquery(
            Filial.objects.filter(
                id=OuterRef('created_by__profile__employee__id_filial')
            ).values('name')[:1],
            output_field=TextField()  # Указываем тип поля явно
        )
    )

    for column in columns:
        queryset = Row.annotate_for_sorting(queryset, column.id, column.data_type)
    return queryset
