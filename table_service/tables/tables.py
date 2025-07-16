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
                accessor=f'filial.name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

            self.base_columns['user'] = tables.Column(
                verbose_name='Пользователь',
                accessor=f'created_by__profile__employee',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

        super().__init__(*args, **kwargs)

    def _add_column(self, column):
        col_name = f'col_{column.id}'
        accessor = f'cell_values.{column.id}'

        column_kwargs = {
            'verbose_name': column.name,
            'accessor': accessor,
            'attrs': {'td': {'class': 'text-center'}},
            'order_by': f'sort_value_{column.id}'
        }

        # Выбор типа колонки
        column_types = {
            Column.ColumnType.BOOLEAN: tables.BooleanColumn,
            Column.ColumnType.DATE: tables.DateColumn,
            Column.ColumnType.EMAIL: tables.EmailColumn,
            Column.ColumnType.URL: tables.URLColumn,
            Column.ColumnType.FILE: tables.FileColumn,
            # Для INTEGER FLOAT и TEXT используем обычный Column
        }

        column_class = column_types.get(column.data_type, tables.Column)
        self.base_columns[col_name] = column_class(**column_kwargs)


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

    def __init__(self, *args, table_obj=None, columns=None, request=None, **kwargs):
        self.base_columns.clear()
        self.table_obj = table_obj
        self.request = request
        if table_obj:
            for column in columns:
                self._add_column(column)

            self.base_columns['filial'] = tables.Column(
                verbose_name=self.get_column_header(None, is_filial=True),
                accessor='filial.name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='filial__name'
            )

            self.base_columns['user'] = tables.Column(
                verbose_name=self.get_column_header(None, is_user=True),
                accessor=f'created_by__profile__employee',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='created_by__profile__employee__secondname'
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
            Column.ColumnType.EMAIL: tables.EmailColumn,
            Column.ColumnType.URL: tables.URLColumn,
            Column.ColumnType.FILE: tables.FileColumn,
            Column.ColumnType.CHOICE: tables.Column
            # Для INTEGER FLOAT и TEXT используем обычный Column
        }

        column_class = column_types.get(column.data_type, tables.Column)
        self.base_columns[col_name] = column_class(**column_kwargs)

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
            edit += format_html(
                '<a class="btn btn-sm btn-danger delete-row-btn"'
                'title="Удалить строку" data-row-id="{}" data-table-id="{}">'
                '<i class="bi bi-x-lg"></i></a>',
                record.id,
                self.table_obj.pk
            )
        return edit

    def get_column_header(self, column=None, is_user=False, is_filial=False):
        edit = format_html('')
        if column and self.table_obj.owner == self.request.user:
            delete_url = reverse('delete_column',
                                 kwargs={
                                     'table_pk': self.table_obj.pk,
                                     'column_pk': column.id
                                 })
            edit_column = reverse('edit_column',
                                  kwargs={
                                      'pk': self.table_obj.pk,
                                      'column_pk': column.id
                                  })
            edit += format_html(
                '<div class="d-flex align-items-center">'
                '<div>{}</div>'
                '<div class="d-flex mr-auto p-2">'
                '<form method="get" action="{}">'
                '<button type="submit" '
                'class="btn btn-sm btn-outline-primary">'
                '<i class="bi bi-pen"></i></button>'
                '</form>'
                '<form method="post" action="{}">{}'
                '<button type="submit" '
                'class="btn btn-sm btn-danger" '
                'onclick="return confirm(\'Удалить столбец?\');">'
                '<i class="bi bi-x-lg"></i></button>'
                '</form>'
                '</div>'
                '</div>',
                column.name,
                edit_column,
                delete_url,
                csrf_input(self.request)
            )
        elif column:
            edit += format_html('<div class="d-flex mr-auto p-2">{}</div>', column.name)
        elif is_user:
            edit += format_html('<div class="d-flex mr-auto p-2">Пользователь</div>')
        elif is_filial:
            edit += format_html('<div class="d-flex mr-auto p-2">Филиал</div>')

        sort_icon = self.render_sort_icon(column, is_user=is_user, is_filial=is_filial)
        return format_html('<div class="d-flex align-items-center">{} {}</div>', sort_icon, edit)

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
                    '<a href="?{}" class="sort-link btn-sm"><i class="{}"></i></a>',
                    params.urlencode(),
                    self.SORT_DOWN_ICON
                )
            else:
                params['sort'] = desc_sort
                return format_html(
                    '<a href="?{}" class="sort-link btn-sm"><i class="{}"></i></a>',
                    params.urlencode(),
                    self.SORT_UP_ICON
                )
        else:
            params['sort'] = asc_sort
            return format_html(
                '<a href="?{}" class="sort-link btn-sm"><i class="{}"></i></a>',
                params.urlencode(),
                self.SORT_ICON
            )
