import datetime

from django.db import models
from django.contrib.auth.models import User
from django.db.models.functions import Concat
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.db.models import IntegerField, FloatField, BooleanField, DateField, F, TextField, Value
from datetime import date


class Filial(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(null=True, blank=True)
    long_name = models.CharField(null=True, blank=True)
    short_name = models.CharField(null=True, blank=True)
    set_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    boss = models.CharField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} (id: {self.id})"


class Employee(models.Model):
    id = models.IntegerField(primary_key=True)
    id_filial = models.IntegerField(null=True, blank=True)
    id_department = models.IntegerField(null=True, blank=True)
    post_name = models.CharField(null=True, blank=True)
    tabnumber = models.IntegerField(unique=True)  # Табельный номер
    firstname = models.CharField(max_length=50)
    secondname = models.CharField(max_length=50)
    lastname = models.CharField(max_length=50)
    set_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.secondname} {self.firstname} {self.lastname}"


class Department(models.Model):
    id = models.IntegerField(primary_key=True)
    id_parent = models.IntegerField(null=True, blank=True)
    id_filial = models.IntegerField(null=True, blank=True)
    name = models.CharField(null=True, blank=True)
    long_name = models.CharField(null=True, blank=True)
    short_name = models.CharField(null=True, blank=True)
    set_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE)
    employee = models.OneToOneField(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profile'
    )


class Table(models.Model):
    title = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    share_token = models.CharField(max_length=32, unique=True, blank=True)
    is_edit_only_you = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = get_random_string(32)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('table_detail', kwargs={'pk': self.pk})

    def get_shared_url(self):
        return reverse('shared_table_view', kwargs={'share_token': self.share_token})

    def get_url_for_users(self):
        return f'/shared/{self.share_token}'

    def is_admin(self, user):
        """Проверяет, является ли пользователь админом таблицы"""
        return Admin.objects.filter(user=user).exists()

    def has_add_permission(self, user):
        """Проверяет, может ли пользователь добавлять строки в таблицу"""
        if self.owner == user:
            return True
        if self.is_admin(user):
            return True

        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)
        query = UserFilial.objects.filter(user=user, table=self)

        for q in query:
            if self.filial_permissions.filter(filial=q.filial, permission_type__in=['RWD', 'RWN']) \
                    and not self.permissions.filter(user=user, filial=q.filial, permission_type__in=['RNN', 'NNN']):
                return True
            if self.permissions.filter(user=user, filial=q.filial,  permission_type__in=['RWD', 'RWN']):
                return True

        if self.filial_permissions.filter(filial=main_filial, permission_type__in=['RWD', 'RWN']) \
                and not self.permissions.filter(user=user, filial=main_filial, permission_type__in=['RNN', 'NNN']):
            return True
        if self.permissions.filter(user=user, filial=main_filial, permission_type__in=['RWD', 'RWN']):
            return True
        return False

    def has_view_permission(self, user):
        """Проверяет, может ли пользователь видеть таблицу"""
        if self.owner == user:
            return True
        if self.is_admin(user):
            return True

        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)
        query = UserFilial.objects.filter(user=user, table=self)

        for q in query:
            if self.filial_permissions.filter(filial=q.filial, permission_type__in=['RWD', 'RWN', 'RNN']) \
                    and not self.permissions.filter(user=user, filial=q.filial,  permission_type='NNN'):
                return True
            if self.permissions.filter(user=user, filial=q.filial,  permission_type__in=['RWD', 'RWN', 'RNN']):
                return True

        if self.filial_permissions.filter(filial=main_filial, permission_type__in=['RWD', 'RWN', 'RNN']) \
                and not self.permissions.filter(user=user, filial=main_filial,  permission_type='NNN'):
            return True
        if self.permissions.filter(user=user, filial=main_filial, permission_type__in=['RWD', 'RWN', 'RNN']):
            return True
        return False

    @classmethod
    def get_shared_tables(cls, user):
        """Возвращает все таблицы, к которым у пользователя есть доступ"""
        if Admin.objects.filter(user=user).exists():
            return cls.objects.all()
        # Таблицы, где пользователь явно указан в TablePermission
        shared_via_permissions = cls.objects.filter(
            permissions__user=user,
        ).distinct()

        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)

        # Таблицы, где главный филиал пользователя явно указан в TableFilialPermission
        shared_via_permissions |= cls.objects.filter(
            filial_permissions__filial=main_filial,
        ).distinct()

        # Таблицы, где доп филиалы пользователя явно указаны в TableFilialPermission
        query = UserFilial.objects.filter(user=user)
        for q in query:
            shared_via_permissions |= cls.objects.filter(
                filial_permissions__filial=q.filial,
            ).distinct()

        return shared_via_permissions

    def __str__(self):
        return self.title


class Admin(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Администратор сервиса'
        verbose_name_plural = 'Администраторы сервиса'


class Column(models.Model):
    class ColumnType(models.TextChoices):
        TEXT = 'text', 'Текст'
        INTEGER = 'integer', 'Целое число'
        FLOAT = 'float', 'Число с плавающей точкой'
        BOOLEAN = 'boolean', 'Логическое'
        DATE = 'date', 'Дата'

    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='columns')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(
        default=False,
        verbose_name="Обязательное поле",
        help_text="Если отмечено, поле должно быть заполнено при создании/редактировании строки"
    )
    data_type = models.CharField(
        max_length=10,
        choices=ColumnType.choices,
        default=ColumnType.TEXT
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.table.title} - {self.name}"


class Row(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='rows')
    order = models.PositiveIntegerField(default=0)
    filial = models.ForeignKey(Filial, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_rows'
    )

    class Meta:
        ordering = ['order']

    def has_edit_permission(self, user):
        """Проверяет, может ли пользователь редактировать строку"""
        if self.table.owner == user:
            return True
        if self.table.is_admin(user):
            return True

        created_by_filial = self.filial

        if TablePermission.objects.filter(user=user, table=self.table, filial=created_by_filial,
                                          permission_type__in=['RNN', 'NNN']):
            return False

        req = TablePermission.objects.filter(user=user, table=self.table, filial=created_by_filial,
                                             permission_type__in=['RWD', 'RWN'])
        if req and not self.table.is_edit_only_you:
            return True
        elif req and self.table.is_edit_only_you and self.created_by == user:
            return True

        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)

        if main_filial == created_by_filial:
            req = TableFilialPermission.objects.filter(filial=main_filial, table=self.table, permission_type__in=['RWD', 'RWN'])
            if req and not self.table.is_edit_only_you:
                return True
            elif req and self.table.is_edit_only_you and self.created_by == user:
                return True

        query = UserFilial.objects.filter(user=user, table=self.table)
        for q in query:
            q_filial = q.filial
            if q_filial == created_by_filial:
                req = TableFilialPermission.objects.filter(filial=q_filial, table=self.table, permission_type__in=['RWD', 'RWN'])
                if req and not self.table.is_edit_only_you:
                    return True
                elif req and self.table.is_edit_only_you and self.created_by == user:
                    return True
        return False

    def has_delete_permission(self, user):
        """Проверяет, может ли пользователь удалять строку"""
        if self.table.owner == user:
            return True
        if self.table.is_admin(user):
            return True

        created_by_filial = self.filial

        if TablePermission.objects.filter(user=user, table=self.table, filial=created_by_filial,
                                          permission_type__in=['RNN', 'RWN', 'NNN']):
            return False

        req = TablePermission.objects.filter(user=user, table=self.table, filial=created_by_filial,
                                             permission_type='RWD')
        if req and not self.table.is_edit_only_you:
            return True
        elif req and self.table.is_edit_only_you and self.created_by == user:
            return True

        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)

        if main_filial == created_by_filial:
            req = TableFilialPermission.objects.filter(filial=main_filial, table=self.table, permission_type='RWD')
            if req and not self.table.is_edit_only_you:
                return True
            elif req and self.table.is_edit_only_you and self.created_by == user:
                return True

        query = UserFilial.objects.filter(user=user, table=self.table)
        for q in query:
            q_filial = q.filial
            if q_filial == created_by_filial:
                req = TableFilialPermission.objects.filter(filial=q_filial, table=self.table, permission_type='RWD')
                if req and not self.table.is_edit_only_you:
                    return True
                elif req and self.table.is_edit_only_you and self.created_by == user:
                    return True
        return False

    @property
    def cell_values(self):
        if not hasattr(self, '_cell_values_cache'):
            cells = self.cells.select_related('column').all()
            self._cell_values_cache = {
                cell.column_id: cell.value
                for cell in cells
            }
        return self._cell_values_cache

    @classmethod
    def get_visible_rows(cls, user, table):
        """Возвращает строки, которые пользователь может видеть"""
        if table.owner == user:
            return table.rows.all()
        if table.is_admin(user):
            return table.rows.all()

        result = cls.objects.none()

        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)

        if (TableFilialPermission.objects.filter(filial=main_filial, table=table,
                                                 permission_type__in=['RWD', 'RWN', 'RNN'])
            and not TablePermission.objects.filter(table=table, user=user, filial=main_filial, permission_type='NNN')) \
                or TablePermission.objects.filter(table=table, user=user, filial=main_filial,permission_type__in=['RWD', 'RWN', 'RNN']):
            result |= cls.objects.filter(table=table, filial__id=main_filial.id).distinct()

        query = UserFilial.objects.filter(user=user, table=table)

        for q in query:
            if (TableFilialPermission.objects.filter(filial=q.filial, table=table,
                                                     permission_type__in=['RWD', 'RWN', 'RNN'])
                and not TablePermission.objects.filter(table=table, user=user, filial=q.filial, permission_type='NNN')) \
                    or TablePermission.objects.filter(table=table, user=user, filial=q.filial, permission_type__in=['RWD', 'RWN', 'RNN']):
                result |= cls.objects.filter(table=table, filial__id=q.filial.id).distinct()

        return result

    @classmethod
    def annotate_for_sorting(cls, queryset, column_id, data_type):
        """Добавляет аннотации для сортировки по типу данных"""
        # Создаем подзапрос для каждого типа данных
        if data_type == Column.ColumnType.INTEGER:
            subquery = Cell.objects.filter(
                row=models.OuterRef('pk'),
                column_id=column_id
            ).values('integer_value')[:1]
            return queryset.annotate(
                **{f'sort_value_{column_id}': models.Subquery(subquery, output_field=IntegerField())}
            )
        elif data_type == Column.ColumnType.FLOAT:
            subquery = Cell.objects.filter(
                row=models.OuterRef('pk'),
                column_id=column_id
            ).values('float_value')[:1]
            return queryset.annotate(
                **{f'sort_value_{column_id}': models.Subquery(subquery, output_field=FloatField())}
            )
        elif data_type == Column.ColumnType.BOOLEAN:
            subquery = Cell.objects.filter(
                row=models.OuterRef('pk'),
                column_id=column_id
            ).values('boolean_value')[:1]
            return queryset.annotate(
                **{f'sort_value_{column_id}': models.Subquery(subquery, output_field=BooleanField())}
            )
        elif data_type == Column.ColumnType.DATE:
            subquery = Cell.objects.filter(
                row=models.OuterRef('pk'),
                column_id=column_id
            ).values('date_value')[:1]
            return queryset.annotate(
                **{f'sort_value_{column_id}': models.Subquery(subquery, output_field=DateField())}
            )
        else:  # TEXT
            queryset = queryset.annotate(
                user_full_name=Concat(
                    F('created_by__profile__employee__secondname'),
                    Value(' '),
                    F('created_by__profile__employee__firstname'),
                    Value(' '),
                    F('created_by__profile__employee__lastname'),
                    output_field=TextField()
                )
            )

            subquery = Cell.objects.filter(
                row=models.OuterRef('pk'),
                column_id=column_id
            ).values('text_value')[:1]
            return queryset.annotate(
                **{f'sort_value_{column_id}': models.Subquery(subquery, output_field=TextField())}
            )


class Cell(models.Model):
    row = models.ForeignKey(Row, on_delete=models.CASCADE, related_name='cells')
    column = models.ForeignKey(Column, on_delete=models.CASCADE)
    # Поля для разных типов данных
    text_value = models.TextField(blank=True, null=True)
    integer_value = models.IntegerField(blank=True, null=True)
    float_value = models.FloatField(blank=True, null=True)
    boolean_value = models.BooleanField(blank=True, null=True)
    date_value = models.DateField(blank=True, null=True)

    class Meta:
        unique_together = ('row', 'column')

    @staticmethod
    def get_default_value(data_type):
        """Возвращает значение по умолчанию для типа данных"""
        defaults = {
            Column.ColumnType.INTEGER: 0,
            Column.ColumnType.FLOAT: 0.0,
            Column.ColumnType.BOOLEAN: False,
            Column.ColumnType.DATE: date.today(),
            Column.ColumnType.TEXT: ''
        }
        return defaults.get(data_type, '')

    @property
    def value(self):
        """Возвращает значение в зависимости от типа колонки"""
        if self.column.data_type == Column.ColumnType.INTEGER:
            return self.integer_value
        elif self.column.data_type == Column.ColumnType.FLOAT:
            return self.float_value
        elif self.column.data_type == Column.ColumnType.BOOLEAN:
            return self.boolean_value
        elif self.column.data_type == Column.ColumnType.DATE:
            return self.date_value
        else:  # TEXT
            return self.text_value

    @value.setter
    def value(self, val):
        """Устанавливает значение в правильное поле"""
        if self.column.data_type == Column.ColumnType.INTEGER:
            self.integer_value = int(val) if val is not None else None
        elif self.column.data_type == Column.ColumnType.FLOAT:
            self.float_value = float(val) if val is not None else None
        elif self.column.data_type == Column.ColumnType.BOOLEAN:
            self.boolean_value = bool(val) if val is not None else None
        elif self.column.data_type == Column.ColumnType.DATE:
            self.date_value = val if val is not None else None  # Здесь val уже datetime.date
        else:  # TEXT
            self.text_value = str(val) if val is not None else ''

    class Meta:
        unique_together = ('row', 'column')

    def __str__(self):
        return f"{self.row} - {self.column}: {self.value}"


class UserFilial(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    filial = models.ForeignKey(Filial, on_delete=models.CASCADE)


class TablePermission(models.Model):
    class PermissionType(models.TextChoices):
        EDIT_VIEW_DELETE = 'RWD', 'Редактировать + Просмотр + Удалять'
        EDIT_VIEW = 'RWN', 'Редактировать + Просмотр'
        VIEW_ONLY = 'RNN', 'Только просмотр'
        NO_ACCESS = 'NNN', 'Нет доступа'
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filial = models.ForeignKey(Filial, on_delete=models.CASCADE, null=True)
    permission_type = models.CharField(
        max_length=3,
        choices=PermissionType.choices,
        default=PermissionType.EDIT_VIEW_DELETE,
        verbose_name='Тип доступа'
    )


class TableFilialPermission(models.Model):
    class PermissionType(models.TextChoices):
        EDIT_VIEW_DELETE = 'RWD', 'Редактировать + Просмотр + Удалять'
        EDIT_VIEW = 'RWN', 'Редактировать + Просмотр'
        VIEW_ONLY = 'RNN', 'Только просмотр'
        NO_ACCESS = 'NNN', 'Нет доступа'
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='filial_permissions')
    filial = models.ForeignKey(Filial, on_delete=models.CASCADE)
    permission_type = models.CharField(
        max_length=3,
        choices=PermissionType.choices,
        default=PermissionType.EDIT_VIEW_DELETE,
        verbose_name='Тип доступа'
    )


class RowLock(models.Model):
    row = models.OneToOneField(
        Row,
        on_delete=models.CASCADE,
        related_name='lock'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='row_locks'
    )
    locked_at = models.DateTimeField()


class TableFilialLock(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='filial_add_permissions')
    filial = models.ForeignKey(Filial, on_delete=models.CASCADE)
    locked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    locked_at = models.DateTimeField()

    class Meta:
        unique_together = ('table', 'filial')
