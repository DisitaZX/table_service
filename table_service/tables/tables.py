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

            self.base_columns['update_user'] = tables.Column(
                verbose_name='Обновлено',
                accessor=f'updated_by__profile__employee',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

            self.base_columns['update_date'] = tables.Column(
                verbose_name='Обновлено',
                accessor=f'last_date',
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
            },
            'th': {
                'style': 'white-space: nowrap;',  # Запрет переноса
            },
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
                verbose_name=self.get_column_header(is_filial=True),
                accessor='filial.name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='filial__name'
            )

            self.base_columns['user'] = tables.Column(
                verbose_name=self.get_column_header(is_user=True),
                accessor=f'created_by__profile__employee',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='created_by__profile__employee__secondname'
            )

            self.base_columns['update_user'] = tables.Column(
                verbose_name=self.get_column_header(is_update_user=True),
                accessor=f'updated_by__profile__employee',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

            self.base_columns['update_date'] = tables.Column(
                verbose_name=self.get_column_header(is_update_time=True),
                accessor=f'last_date',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

            self.base_columns['actions'] = tables.Column(
                empty_values=(),
                orderable=False,
                verbose_name='',
                attrs={
                    'td': {
                        'class': 'text-center',
                        'style': 'white-space: nowrap;',  # Фиксация ширины и содержимого
                    },
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

    def render_column_header(self, column):
        """Рендерит заголовок колонки с фильтром для всех типов данных"""
        if not column:
            return ""

        filter_html = ""
        current_filter = self.request.GET.get(f'filter_{column.id}', '')

        if column.data_type == Column.ColumnType.CHOICE and column.choices:
            # Фильтр для колонок с выбором из списка
            filter_html = self._render_choice_filter(column, current_filter)
        elif column.data_type == Column.ColumnType.BOOLEAN:
            # Фильтр для булевых значений
            filter_html = self._render_boolean_filter(column, current_filter)
        elif column.data_type in [Column.ColumnType.INTEGER, Column.ColumnType.FLOAT,
                                  Column.ColumnType.POSITIVE_INTEGER]:
            # Фильтр для числовых значений
            filter_html = self._render_number_filter(column, current_filter)
        elif column.data_type == Column.ColumnType.DATE:
            # Фильтр для дат
            filter_html = self._render_date_filter(column, current_filter)
        elif column.data_type in [Column.ColumnType.URL, Column.ColumnType.EMAIL,
                                  Column.ColumnType.TEXT]:
            # Фильтр для текстовых значений (TEXT, EMAIL, URL)
            filter_html = self._render_text_filter(column, current_filter)

        return format_html(filter_html)

    def _render_choice_filter(self, column, current_filter):
        """Рендерит фильтр для колонок с выбором из списка"""
        return f"""
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                    id="dropdownMenuButton_{column.id}" data-bs-toggle="dropdown" 
                    aria-expanded="false">
                <i class="bi bi-funnel"></i>
            </button>
            <ul class="dropdown-menu" aria-labelledby="dropdownMenuButton_{column.id}">
                <li><a class="dropdown-item {'active' if not current_filter else ''}" 
                       href="?{self._get_filter_query(column.id, '')}">Все</a></li>
                {"".join([
            f'<li><a class="dropdown-item {"active" if current_filter == choice else ""}" '
            f'href="?{self._get_filter_query(column.id, choice)}">{choice}</a></li>'
            for choice in column.choices
        ])}
            </ul>
        </div>
        """

    def _render_boolean_filter(self, column, current_filter):
        """Рендерит фильтр для булевых значений"""
        return f"""
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                    id="dropdownMenuButton_{column.id}" data-bs-toggle="dropdown" 
                    aria-expanded="false">
                <i class="bi bi-funnel"></i>
            </button>
            <ul class="dropdown-menu" aria-labelledby="dropdownMenuButton_{column.id}">
                <li><a class="dropdown-item {'active' if not current_filter else ''}" 
                       href="?{self._get_filter_query(column.id, '')}">Все</a></li>
                <li><a class="dropdown-item {'active' if current_filter == 'true' else ''}" 
                       href="?{self._get_filter_query(column.id, 'true')}">Да</a></li>
                <li><a class="dropdown-item {'active' if current_filter == 'false' else ''}" 
                       href="?{self._get_filter_query(column.id, 'false')}">Нет</a></li>
            </ul>
        </div>
        """

    def _render_number_filter(self, column, current_filter):
        """Рендерит фильтр для числовых значений"""
        min_value = self.request.GET.get(f'filter_{column.id}_min', '')
        max_value = self.request.GET.get(f'filter_{column.id}_max', '')

        return f"""
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                    id="dropdownMenuButton_{column.id}" data-bs-toggle="dropdown" 
                    aria-expanded="false">
                <i class="bi bi-funnel"></i>
            </button>
            <div class="dropdown-menu p-2" aria-labelledby="dropdownMenuButton_{column.id}" style="min-width: 250px;">
                <form method="get" action="?" class="filter-form">
                    <input type="hidden" name="filter_column" value="{column.id}">
                    <div class="mb-2">
                        <label class="form-label">От</label>
                        <input type="number" name="filter_{column.id}_min" 
                               value="{min_value}" 
                               class="form-control form-control-sm">
                    </div>
                    <div class="mb-2">
                        <label class="form-label">До</label>
                        <input type="number" name="filter_{column.id}_max" 
                               value="{max_value}" 
                               class="form-control form-control-sm">
                    </div>
                    <div class="d-flex justify-content-between">
                        <button type="submit" class="btn btn-sm btn-primary">Применить</button>
                        <a href="?{self._get_filter_query(column.id, None)}" class="btn btn-sm btn-outline-secondary">Сбросить</a>
                    </div>
                </form>
            </div>
        </div>
        """

    def _render_date_filter(self, column, current_filter):
        """Рендерит фильтр для дат"""
        start_date = self.request.GET.get(f'filter_{column.id}_start', '')
        end_date = self.request.GET.get(f'filter_{column.id}_end', '')

        return f"""
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                    id="dropdownMenuButton_{column.id}" data-bs-toggle="dropdown" 
                    aria-expanded="false">
                <i class="bi bi-funnel"></i>
            </button>
            <div class="dropdown-menu p-2" aria-labelledby="dropdownMenuButton_{column.id}" style="min-width: 250px;">
                <form method="get" action="?" class="filter-form">
                    <input type="hidden" name="filter_column" value="{column.id}">
                    <div class="mb-2">
                        <label class="form-label">От</label>
                        <input type="date" name="filter_{column.id}_start" 
                               value="{start_date}" 
                               class="form-control form-control-sm">
                    </div>
                    <div class="mb-2">
                        <label class="form-label">До</label>
                        <input type="date" name="filter_{column.id}_end" 
                               value="{end_date}" 
                               class="form-control form-control-sm">
                    </div>
                    <div class="d-flex justify-content-between">
                        <button type="submit" class="btn btn-sm btn-primary">Применить</button>
                        <a href="?{self._get_filter_query(column.id, None)}" class="btn btn-sm btn-outline-secondary">Сбросить</a>
                    </div>
                </form>
            </div>
        </div>
        """

    def _render_text_filter(self, column, current_filter):
        """Рендерит фильтр для текстовых значений"""
        return f"""
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                    id="dropdownMenuButton_{column.id}" data-bs-toggle="dropdown" 
                    aria-expanded="false">
                <i class="bi bi-funnel"></i>
            </button>
            <div class="dropdown-menu p-2" aria-labelledby="dropdownMenuButton_{column.id}" style="min-width: 250px;">
                <form method="get" action="?" class="filter-form">
                    <input type="hidden" name="filter_column" value="{column.id}">
                    <div class="mb-2">
                        <input type="text" name="filter_{column.id}" 
                               value="{current_filter}" 
                               placeholder="Фильтр..."
                               class="form-control form-control-sm">
                    </div>
                    <div class="d-flex justify-content-between">
                        <button type="submit" class="btn btn-sm btn-primary">Применить</button>
                        <a href="?{self._get_filter_query(column.id, '')}" class="btn btn-sm btn-outline-secondary">Сбросить</a>
                    </div>
                </form>
            </div>
        </div>
        """

    def _get_filter_query(self, column_id, value):
        """Генерирует GET-запрос с фильтром для колонки, сохраняя другие фильтры"""
        params = self.request.GET.copy()

        # Удаляем все параметры фильтрации для текущей колонки
        keys_to_remove = [
            f'filter_{column_id}',
            f'filter_{column_id}_min',
            f'filter_{column_id}_max',
            f'filter_{column_id}_start',
            f'filter_{column_id}_end'
        ]

        for key in keys_to_remove:
            if key in params:
                del params[key]

        # Если передано значение (не сброс фильтра), добавляем соответствующие параметры
        if value:
            if isinstance(value, dict):  # Для сложных фильтров (диапазоны)
                for k, v in value.items():
                    if v:  # Добавляем только непустые значения
                        params[f'filter_{column_id}_{k}'] = v
            else:  # Для простых фильтров (одиночное значение)
                params[f'filter_{column_id}'] = value

        return params.urlencode()

    def get_column_header(self, column=None, is_user=False, is_filial=False, is_update_user=False, is_update_time=False):
        """Возвращает HTML для заголовка колонки с кнопками редактирования и фильтрацией"""
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
        elif is_update_user:
            edit += format_html('<div class="d-flex mr-auto p-2">Обновивший пользователь</div>')
        elif is_update_time:
            edit += format_html('<div class="d-flex mr-auto p-2">Дата обновления</div>')

        sort_icon = self.render_sort_icon(column, is_user=is_user, is_filial=is_filial, is_update_user=is_update_user,
                                          is_update_time=is_update_time)
        filter_icon = self.render_column_header(column) if column else ''

        return format_html(
            '<div class="d-flex align-items-center">{} {} {}</div>',
            sort_icon,
            edit,
            filter_icon
        )

    def _get_sort_params(self, column=None, is_user=False, is_filial=False, is_update_user=False, is_update_time=False):
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
        elif is_update_user:
            return {
                'sort_field': 'update_user',
                'asc_sort': 'update_user',
                'desc_sort': '-update_user'
            }
        elif is_update_time:
            return {
                'sort_field': 'update_time',
                'asc_sort': 'update_time',
                'desc_sort': '-update_time'
            }
        return None

    def render_sort_icon(self, column=None, is_user=False, is_filial=False, is_update_user=False, is_update_time=False):
        sort_params = None

        if column:
            sort_params = self._get_sort_params(column=column)
        elif is_user:
            sort_params = self._get_sort_params(is_user=is_user)  # Для колонки user
        elif is_filial:
            sort_params = self._get_sort_params(is_filial=is_filial)  # Для колонки filial
        elif is_update_user:
            sort_params = self._get_sort_params(is_update_user=is_update_user)  # Для колонки filial
        elif is_update_time:
            sort_params = self._get_sort_params(is_update_time=is_update_time)  # Для колонки filial

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
