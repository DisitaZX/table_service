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
                verbose_name=self.get_column_header('is_filial'),
                accessor='filial.name',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='filial__name'
            )

            self.base_columns['user'] = tables.Column(
                verbose_name=self.get_column_header('is_user'),
                accessor=f'created_by__profile__employee',
                attrs={
                    'td': {'class': 'text-center'}
                },
                order_by='created_by__profile__employee__secondname'
            )

            self.base_columns['update_user'] = tables.Column(
                verbose_name=self.get_column_header('is_update_user'),
                accessor=f'updated_by__profile__employee',
                attrs={
                    'td': {'class': 'text-center'}
                },
                orderable=False,
            )

            self.base_columns['update_date'] = tables.Column(
                verbose_name=self.get_column_header('is_update_time'),
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
                        <a href="?{self._get_filter_query(column.id, '')}" class="btn btn-sm btn-outline-secondary">Сбросить</a>
                    </div>
                </form>
            </div>
        </div>
        """

    def _render_date_filter(self, column, current_filter):
        """Рендерит фильтр для дат"""
        if isinstance(column, Column):
            field_name = column.id
        else:
            field_name = column

        start_date = self.request.GET.get(f'filter_{field_name}_start', '')
        end_date = self.request.GET.get(f'filter_{field_name}_end', '')

        return f"""
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                    id="dropdownMenuButton_{field_name}" data-bs-toggle="dropdown" 
                    aria-expanded="false">
                <i class="bi bi-funnel"></i>
            </button>
            <div class="dropdown-menu p-2" aria-labelledby="dropdownMenuButton_{field_name}" style="min-width: 250px;">
                <form method="get" action="?" class="filter-form">
                    <input type="hidden" name="filter_column" value="{field_name}">
                    <div class="mb-2">
                        <label class="form-label">От</label>
                        <input type="date" name="filter_{field_name}_start" 
                               value="{start_date}" 
                               class="form-control form-control-sm">
                    </div>
                    <div class="mb-2">
                        <label class="form-label">До</label>
                        <input type="date" name="filter_{field_name}_end" 
                               value="{end_date}" 
                               class="form-control form-control-sm">
                    </div>
                    <div class="d-flex justify-content-between">
                        <button type="submit" class="btn btn-sm btn-primary">Применить</button>
                        <a href="?{self._get_filter_query(field_name, '')}" class="btn btn-sm btn-outline-secondary">Сбросить</a>
                    </div>
                </form>
            </div>
        </div>
        """

    def _render_text_filter(self, column, current_filter):
        if isinstance(column, Column):
            field_name = column.id
        else:
            field_name = column

        """Рендерит фильтр для текстовых значений"""
        return f"""
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                    id="dropdownMenuButton_{field_name}" data-bs-toggle="dropdown" 
                    aria-expanded="false">
                <i class="bi bi-funnel"></i>
            </button>
            <div class="dropdown-menu p-2" aria-labelledby="dropdownMenuButton_{field_name}" style="min-width: 250px;">
                <form method="get" action="?" class="filter-form">
                    <div class="mb-2">
                        <input type="text" name="filter_{field_name}" 
                               value="{current_filter}" 
                               placeholder="Фильтр..."
                               class="form-control form-control-sm">
                    </div>
                    <div class="d-flex justify-content-between">
                        <button type="submit" class="btn btn-sm btn-primary">Применить</button>
                        <a href="?{self._get_filter_query(field_name, '')}" class="btn btn-sm btn-outline-secondary">Сбросить</a>
                    </div>
                </form>
            </div>
        </div>
        """

    def get_reset_filters_url(self):
        """Возвращает URL для сброса ВСЕХ фильтров (оставляет сортировку и другие параметры)"""
        params = self.request.GET.copy()

        # Удаляем все параметры, начинающиеся с 'filter_'
        filter_keys = [key for key in params.keys() if key.startswith('filter_')]
        for key in filter_keys:
            del params[key]

        return f"?{params.urlencode()}" if params else "?"

    def _get_filter_query(self, column_id, value):
        """Генерирует GET-запрос с фильтром для колонки, сохраняя другие фильтры"""
        params = self.request.GET.copy()
        # Если передано значение (не сброс фильтра), добавляем соответствующие параметры
        if value:
            if isinstance(value, dict):  # Для сложных фильтров (диапазоны)
                for k, v in value.items():
                    if v:  # Добавляем только непустые значения
                        params[f'filter_{column_id}_{k}'] = v
            else:  # Для простых фильтров (одиночное значение)
                params[f'filter_{column_id}'] = value
        else:
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
        return params.urlencode()

    def get_column_header(self, column):
        """Возвращает HTML для заголовка колонки с кнопками редактирования и фильтрацией"""
        edit = format_html('')

        if isinstance(column, Column) and self.table_obj.owner == self.request.user:
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
        elif isinstance(column, Column):
            edit += format_html('<div class="d-flex mr-auto p-2">{}</div>', column.name)
        elif column == 'is_user':
            edit += format_html('<div class="d-flex mr-auto p-2">Пользователь</div>')
        elif column == 'is_filial':
            edit += format_html('<div class="d-flex mr-auto p-2">Филиал</div>')
        elif column == 'is_update_user':
            edit += format_html('<div class="d-flex mr-auto p-2">Обновивший пользователь</div>')
        elif column == 'is_update_time':
            edit += format_html('<div class="d-flex mr-auto p-2">Дата обновления</div>')

        sort_icon = self.render_sort_icon(column)
        if isinstance(column, Column):
            filter_icon = self.render_column_header(column)
        elif column == 'is_update_time':
            current_filter = None
            filter_icon = format_html(self._render_date_filter(column, current_filter))
        else:
            current_filter = self.request.GET.get(f'filter_{column}', '')
            filter_icon = format_html(self._render_text_filter(column, current_filter))

        return format_html(
            '<div class="d-flex align-items-center">{} {} {}</div>',
            sort_icon,
            edit,
            filter_icon
        )

    def _get_sort_params(self, column):
        if isinstance(column, Column):  # Для обычных колонок таблицы
            return {
                'sort_field': f'col_{column.id}',
                'asc_sort': f'col_{column.id}',
                'desc_sort': f'-col_{column.id}'
            }
        elif column == 'is_user':  # Для колонки пользователя
            return {
                'sort_field': 'user',
                'asc_sort': 'user',
                'desc_sort': '-user'
            }
        elif column == 'is_filial':  # Для колонки филиала
            return {
                'sort_field': 'filial',
                'asc_sort': 'filial',
                'desc_sort': '-filial'
            }
        elif column == 'is_update_user':
            return {
                'sort_field': 'update_user',
                'asc_sort': 'update_user',
                'desc_sort': '-update_user'
            }
        elif column == 'is_update_time':
            return {
                'sort_field': 'update_time',
                'asc_sort': 'update_time',
                'desc_sort': '-update_time'
            }
        return None

    def render_sort_icon(self, column):
        sort_params = None

        if column:
            sort_params = self._get_sort_params(column)

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
