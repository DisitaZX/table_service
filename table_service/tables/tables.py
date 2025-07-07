import django_tables2 as tables
from django.template.backends.utils import csrf_input
from django.urls import reverse
from django.utils.html import format_html
from .models import Row, Column


class ExportTable(tables.Table):
    export_formats = ['xls', 'xlsx', 'csv']

    class Meta:
        model = Row
        attrs = {
            'class': 'table table-bordered table-hover',
            'thead': {
                'class': 'table-light'
            }
        }
        fields = ()  # Будем заполнять динамически

    def __init__(self, *args, table_obj=None, request=None, **kwargs):
        self.base_columns.clear()
        self.table_obj = table_obj
        self.request = request
        if table_obj:
            for column in table_obj.columns.all():
                self._add_column(column)
            self.base_columns['filial'] = tables.Column(
                verbose_name='Филиал',
                accessor=f'filial_values.name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

            self.base_columns['user'] = tables.Column(
                verbose_name='Пользователь',
                accessor=f'user_values.full_name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

        super().__init__(*args, **kwargs)

    def _add_column(self, column):
        col_name = f'col_{column.id}'
        accessor = f'cell_values.{column.id}'

        # Выбираем соответствующий тип столбца
        if column.data_type == Column.ColumnType.INTEGER:
            self.base_columns[col_name] = tables.Column(
                verbose_name=column.name,
                accessor=accessor,
                attrs={'td': {'class': 'text-center'}},
                orderable=False,
            )
        if column.data_type == Column.ColumnType.FLOAT:
            self.base_columns[col_name] = tables.Column(
                verbose_name=column.name,
                accessor=accessor,
                attrs={'td': {'class': 'text-center'}},
                orderable=False,
            )
        elif column.data_type == Column.ColumnType.BOOLEAN:
            self.base_columns[col_name] = tables.BooleanColumn(
                verbose_name=column.name,
                accessor=accessor,
                attrs={'td': {'class': 'text-center'}},
                orderable=False,
            )
        elif column.data_type == Column.ColumnType.DATE:
            self.base_columns[col_name] = tables.DateColumn(
                verbose_name=column.name,
                accessor=accessor,
                attrs={'td': {'class': 'text-center'}},
                orderable=False,
            )
        else:  # TEXT по умолчанию
            self.base_columns[col_name] = tables.Column(
                verbose_name=column.name,
                accessor=accessor,
                attrs={'td': {'class': 'text-center'}},
                orderable=False,
            )


class DynamicTable(tables.Table):
    SORT_ICON = 'fa-solid fa-sort'
    SORT_UP_ICON = 'fa-solid fa-sort-up'
    SORT_DOWN_ICON = 'fa-solid fa-sort-down'

    class Meta:
        model = Row
        attrs = {
            'class': 'table table-bordered table-hover',
            'thead': {
                'class': 'table-light'
            }
        }
        fields = ()  # Будем заполнять динамически

    def __init__(self, *args, table_obj=None, request=None, **kwargs):
        self.base_columns.clear()
        self.table_obj = table_obj
        self.request = request
        if table_obj:
            for column in table_obj.columns.all():
                self._add_column(column)

            self.base_columns['filial'] = tables.Column(
                verbose_name=self.get_column_header(None, is_filial=True),
                accessor=f'filial_values.name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='filial_name'
            )

            self.base_columns['user'] = tables.Column(
                verbose_name=self.get_column_header(None, is_user=True),
                accessor=f'user_values.full_name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='user_full_name'
            )
            self.base_columns['actions'] = tables.Column(
                empty_values=(),
                orderable=False,
                verbose_name='',
                attrs={
                    'td': {'class': 'text-center',
                           'width': '125px'}
                }
            )
        super().__init__(*args, **kwargs)

    def _add_column(self, column):
        col_name = f'col_{column.id}'
        accessor = f'cell_values.{column.id}'

        column_kwargs = {
            'verbose_name': self.get_column_header(column),
            'accessor': accessor,
            'attrs': {'td': {'class': 'text-center'}},
            'order_by': f'sort_value_{column.id}'
        }

        # Выбор типа колонки
        column_types = {
            Column.ColumnType.BOOLEAN: tables.BooleanColumn,
            Column.ColumnType.DATE: tables.DateColumn,
            # Для INTEGER FLOAT и TEXT используем обычный Column
        }

        column_class = column_types.get(column.data_type, tables.Column)
        self.base_columns[col_name] = column_class(**column_kwargs)

    def render_delete(self, record):
        if (self.table_obj.owner == self.request.user) or (record.has_delete_permission(self.request.user)):
            delete_url = reverse('delete_row',
                                 kwargs={'table_pk': self.table_obj.pk,
                                         'row_pk': record.id
                                         })
            return format_html(
                '<form method="post" action="{}" style="display:inline;">{}'
                '<button type="submit" '
                'class="btn btn-sm btn-danger" '
                'onclick="return confirm(\'Удалить строку?\');">'
                '×</button>'
                '</form>',
                delete_url,
                csrf_input(self.request)
            )
        return ''

    def render_actions(self, record):
        edit = format_html('')
        if record.has_edit_permission(self.request.user):
            edit += format_html(
                '<a class="btn btn-sm btn-outline-primary edit-row-btn" '
                'title="Редактировать строку"'
                'data-row-id="{}" data-table-id="{}"><i class="bi bi-pen"></i>'
                '</a>',
                record.id,
                self.table_obj.pk
            )
        if record.has_delete_permission(self.request.user):
            delete_url = reverse('delete_row',
                                 kwargs={'table_pk': self.table_obj.pk,
                                         'row_pk': record.id
                                         })
            edit += format_html(
                '<form method="post" action="{}" style="display:inline;">{}'
                '<button type="submit" '
                'class="btn btn-sm btn-danger" '
                'onclick="return confirm(\'Удалить строку?\');">'
                '<i class="bi bi-x-lg"></i></button>'
                '</form>',
                delete_url,
                csrf_input(self.request)
            )

        if record.has_manage_permission(self.request.user):
            edit += format_html(
                '<a href="{}" class="btn btn-sm btn-outline-secondary" title="Настроить разрешения">'
                '<i class="bi bi-people-fill"></i></a>',
                reverse('manage_row_permissions', kwargs={
                    'table_pk': self.table_obj.pk,
                    'row_pk': record.id
                })
            )
        return edit

    def get_column_header(self, column=None, is_user=False, is_filial=False):
        edit = format_html('')
        if column and self.table_obj.owner == self.request.user:
            delete_url = reverse('delete_column',
                                 kwargs={'table_pk': self.table_obj.pk,
                                         'column_pk': column.id
                                         })
            edit += format_html(
                '<div class="d-flex justify-content-between align-items-center">'
                '<div>{}</div>'
                '<div>'
                '<form method="post" action="{}" style="display:inline;">{}'
                '<button type="submit" '
                'class="btn btn-sm btn-danger ms-3" '
                'onclick="return confirm(\'Удалить столбец?\');">'
                '<i class="bi bi-x-lg"></i></button>'
                '</form>'
                '</div>'
                '</div>',
                column.name,
                delete_url,
                csrf_input(self.request)
            )
        elif column:
            edit += format_html('<div>{}</div>', column.name)
        elif is_user:
            edit += format_html('<div>Пользователь</div>')
        elif is_filial:
            edit += format_html('<div>Филиал</div>')

        sort_icon = self.render_sort_icon(column, is_user=is_user, is_filial=is_filial)
        return format_html('{} {}', sort_icon, edit)

    def _get_sort_params(self, column=None, is_user=False, is_filial=False):
        if column:  # Для обычных колонок таблицы
            return {
                'sort_field': f'col_{column.id}',
                'asc_sort': f'col_{column.id}',
                'desc_sort': f'-col_{column.id}'
            }
        elif is_user:  # Для колонки пользователя
            return {
                'sort_field': 'user',
                'asc_sort': 'user',
                'desc_sort': '-user'
            }
        elif is_filial:  # Для колонки филиала
            return {
                'sort_field': 'filial',
                'asc_sort': 'filial',
                'desc_sort': '-filial'
            }
        return None

    def render_sort_icon(self, column=None, is_user=False, is_filial=False):
        sort_params = None

        if column:
            sort_params = self._get_sort_params(column=column)
        elif is_user:
            sort_params = self._get_sort_params(is_user=is_user)  # Для колонки user
        elif is_filial:
            sort_params = self._get_sort_params(is_filial=is_filial)  # Для колонки filial

        if not sort_params:
            return ''

        sort_field = sort_params['sort_field']
        asc_sort = sort_params['asc_sort']
        desc_sort = sort_params['desc_sort']

        sort_param = self.request.GET.get('sort', '')

        params = self.request.GET.copy()

        if sort_param.lstrip('-') == sort_field:
            if sort_param.startswith('-'):
                if 'sort' in params:
                    del params['sort']
                return format_html(
                    '<a href="?{}" class="sort-link"><i class="{}"></i></a>',
                    params.urlencode(),
                    self.SORT_DOWN_ICON
                )
            else:
                params['sort'] = desc_sort
                return format_html(
                    '<a href="?{}" class="sort-link"><i class="{}"></i></a>',
                    params.urlencode(),
                    self.SORT_UP_ICON
                )
        else:
            params['sort'] = asc_sort
            return format_html(
                '<a href="?{}" class="sort-link"><i class="{}"></i></a>',
                params.urlencode(),
                self.SORT_ICON
            )
