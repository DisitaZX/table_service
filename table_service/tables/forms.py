from django import forms
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe

from .models import Table, Column, Cell, Filial, TablePermission, TableFilialPermission, UserFilial


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ['title', 'is_edit_only_you']

        widgets = {
            'is_edit_only_you': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }


class ColumnForm(forms.ModelForm):
    class Meta:
        model = Column
        fields = ['name', 'data_type', 'is_required', 'choices']
        widgets = {
            'data_type': forms.Select(choices=Column.ColumnType.choices),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    choice_options = forms.CharField(
        required=False,
        label="Варианты выбора:",
        widget=forms.TextInput(attrs={
            'placeholder': 'Вариант 1; Вариант 2; Вариант 3'
        }),
        help_text='Введите варианты через точку с запятой (;)'
    )
    labels = {
        'is_required': 'Обязательное поле'
    }

    def __init__(self, *args, **kwargs):
        self.table = kwargs.pop('table', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        choice_options = cleaned_data.get('choice_options')
        if choice_options:
            # Разделяем строку по ";" и убираем пустые значения
            choices = [opt.strip() for opt in choice_options.split(";") if opt.strip()]
            cleaned_data["choices"] = choices


class ColumnEditForm(forms.ModelForm):
    class Meta:
        model = Column
        fields = ['name', 'order', 'data_type', 'is_required', 'choices']
        widgets = {
            'order': forms.NumberInput(attrs={'min': 0}),
            'data_type': forms.Select(choices=Column.ColumnType.choices),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    labels = {
        'is_required': 'Обязательное поле'
    }
    choice_options = forms.CharField(
        required=False,
        label="Варианты выбора:",
        widget=forms.TextInput(attrs={
            'placeholder': 'Вариант 1; Вариант 2; Вариант 3'
        }),
        help_text='Введите варианты через точку с запятой (;)'
    )

    def __init__(self, *args, **kwargs):
        self.table = kwargs.pop('table', None)
        super().__init__(*args, **kwargs)

        if self.instance.choices:
            self.initial['choice_options'] = ";".join(self.instance.choices)

    def clean_order(self):
        order = self.cleaned_data['order']
        if self.table:
            old_order = self.instance.order if self.instance else None
            # Проверяем, занят ли этот порядок другой колонкой
            conflicting_columns = Column.objects.filter(
                table=self.table,
                order=order
            ).exclude(pk=self.instance.pk if self.instance else None)
            for col in conflicting_columns:
                col.order = old_order
                col.save()

        return order

    def clean(self):
        cleaned_data = super().clean()
        choice_options = cleaned_data.get('choice_options')
        if choice_options:
            # Разделяем строку по ";" и убираем пустые значения
            choices = [opt.strip() for opt in choice_options.split(";") if opt.strip()]
            cleaned_data["choices"] = choices


class TablePermissionForm(forms.ModelForm):
    class Meta:
        model = TablePermission
        fields = ['filial', 'permission_type']
        widgets = {
            'permission_type': forms.Select(attrs={
                'class': 'form-select'
            })
        }


class TableFilialPermissionForm(forms.ModelForm):
    class Meta:
        model = TableFilialPermission
        fields = ['permission_type']
        widgets = {
            'permission_type': forms.Select(attrs={
                'class': 'form-select'
            })
        }


class UserFilialForm(forms.ModelForm):
    class Meta:
        model = UserFilial
        fields = ['user', 'filial']


class PermissionUserFilialForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'userSelect'
        })
    )
    filial = forms.ModelChoiceField(
        queryset=Filial.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filialSelect'
        })
    )

    def __init__(self, *args, **kwargs):
        table = kwargs.pop('table', None)
        super().__init__(*args, **kwargs)
        if table:
            self.fields['filial'].queryset = Filial.objects.all()
            self.fields['user'].queryset = User.objects.all()


class PermissionUserForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'userSelect',
            'onchange': 'updateFilialOptions(this.value)'
        })
    )
    filial = forms.ModelChoiceField(
        queryset=Filial.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filialSelect'
        })
    )

    def __init__(self, *args, **kwargs):
        table = kwargs.pop('table', None)
        super().__init__(*args, **kwargs)
        if table:
            self.fields['user'].queryset = User.objects.all().select_related('profile__employee').order_by(
                'profile__employee__lastname',
                'profile__employee__firstname',
                'profile__employee__secondname'
            )

            self.fields['filial'].queryset = Filial.objects.none()

            # Если форма передана с данными выбранного пользователя
            if 'user' in self.data:
                try:
                    user_id = int(self.data.get('user'))
                    user = User.objects.get(id=user_id)
                    self.set_filial_queryset(user, table)
                except (ValueError, User.DoesNotExist):
                    pass

    def set_filial_queryset(self, user, table):
        """Устанавливает queryset филиалов для конкретного пользователя"""
        # Получаем основной филиал пользователя
        main_filial = Filial.objects.get(id=user.profile.employee.id_filial)

        # Получаем дополнительные филиалы пользователя для этой таблицы
        additional_filials = UserFilial.objects.filter(
            user=user,
            table=table
        ).values_list('filial', flat=True)
        # Собираем все филиалы пользователя
        filial_ids = [main_filial.id] + list(additional_filials)

        # Устанавливаем queryset для поля filial
        self.fields['filial'].queryset = Filial.objects.filter(id__in=filial_ids)


class PermissionFilialForm(forms.Form):
    filial = forms.ModelChoiceField(
        queryset=Filial.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filialSelect'
        })
    )

    def __init__(self, *args, **kwargs):
        table = kwargs.pop('table', None)
        super().__init__(*args, **kwargs)
        if table:
            self.fields['filial'].queryset = Filial.objects.all()


class AddRowForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.table = kwargs.pop('table', None)
        self.columns = kwargs.pop('columns', None)
        self.available_filials = kwargs.pop('available_filials', None)
        super().__init__(*args, **kwargs)

        if self.user and self.table:
            self.fields['filial'] = forms.ModelChoiceField(
                queryset=self.available_filials,
                label="Филиал",
                required=True,
                widget=forms.Select(attrs={
                    'class': 'form-select',
                }),
                initial=self.user.profile.employee.id_filial
            )
            for column in self.columns:
                field_name = f'col_{column.id}'

                required = column.is_required
                initial_value = Cell.get_default_value(column.data_type) if not required else None

                if column.data_type == Column.ColumnType.INTEGER:
                    self.fields[field_name] = forms.IntegerField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'step': '1',
                            'min': '-2147483648',
                            'max': '2147483647',
                            'placeholder': 'Введите целое число'
                        }),
                    )
                elif column.data_type == Column.ColumnType.POSITIVE_INTEGER:
                    self.fields[field_name] = forms.IntegerField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'step': '1',
                            'min': '0',
                            'max': '2147483647',
                            'placeholder': 'Введите целое число больше 0'
                        }),
                    )
                elif column.data_type == Column.ColumnType.CHOICE:
                    choices_list = column.choices if column.choices else []
                    choices = [(item, item) for item in choices_list]
                    self.fields[field_name] = forms.ChoiceField(
                        label=column.name,
                        required=required,
                        choices=choices,
                        initial=initial_value,
                        widget=forms.Select(attrs={
                            'class': 'form-control',
                        }),
                    )
                elif column.data_type == Column.ColumnType.EMAIL:
                    self.fields[field_name] = forms.EmailField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.EmailInput(attrs={
                            'class': 'form-control',
                            'placeholder': 'Введите Email'
                        }),
                    )
                elif column.data_type == Column.ColumnType.URL:
                    self.fields[field_name] = forms.URLField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.URLInput(attrs={
                            'class': 'form-control',
                            'placeholder': 'Введите ссылку'
                        }),
                    )
                elif column.data_type == Column.ColumnType.FILE:
                    self.fields[field_name] = forms.FileField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.FileInput(attrs={
                            'class': 'form-control',
                            'placeholder': 'Загрузите файл'
                        }),
                    )
                elif column.data_type == Column.ColumnType.FLOAT:
                    self.fields[field_name] = forms.FloatField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'step': '0.01',
                            'placeholder': 'Введите число с плавающей точкой'
                        }),
                    )
                elif column.data_type == Column.ColumnType.BOOLEAN:
                    self.fields[field_name] = forms.BooleanField(
                        label=column.name,
                        initial=initial_value,
                        required=required,
                        widget=forms.CheckboxInput(attrs={
                            'class': 'form-check-input'
                        })
                    )
                elif column.data_type == Column.ColumnType.DATE:
                    self.fields[field_name] = forms.DateField(
                        label=column.name,
                        required=required,
                        initial=str(initial_value),
                        widget=forms.DateInput(attrs={
                            'type': 'date',
                            'class': 'form-control',
                            'placeholder': 'Выберите дату'
                        }),
                    )
                else:  # TEXT
                    self.fields[field_name] = forms.CharField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.TextInput(attrs={
                            'class': 'form-control',
                            'placeholder': 'Введите текст'
                        }),
                    )


class RowEditForm(forms.Form):
    def __init__(self, *args, columns, **kwargs):
        self.row = kwargs.pop('row', None)
        super().__init__(*args, **kwargs)

        if self.row:
            for column in columns:
                cell = self.row.cells.filter(column=column).first()
                if cell:
                    initial_value = cell.value
                else:
                    initial_value = ''

                field_name = f'col_{column.id}'
                required = column.is_required
                if column.data_type == Column.ColumnType.INTEGER:
                    self.fields[field_name] = forms.IntegerField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'step': '1',
                            'min': '-2147483648',
                            'max': '2147483647',
                            'placeholder': 'Введите целое число'
                        }),
                    )
                elif column.data_type == Column.ColumnType.POSITIVE_INTEGER:
                    self.fields[field_name] = forms.IntegerField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'step': '1',
                            'min': '0',
                            'max': '2147483647',
                            'placeholder': 'Введите целое число больше 0'
                        }),
                    )
                elif column.data_type == Column.ColumnType.EMAIL:
                    self.fields[field_name] = forms.EmailField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.EmailInput(attrs={
                            'class': 'form-control',
                            'placeholder': 'Введите Email'
                        }),
                    )
                elif column.data_type == Column.ColumnType.CHOICE:
                    choices_list = column.choices if column.choices else []
                    choices = [(item, item) for item in choices_list]
                    self.fields[field_name] = forms.ChoiceField(
                        label=column.name,
                        required=required,
                        choices=choices,
                        initial=initial_value,
                        widget=forms.Select(attrs={
                            'class': 'form-control',
                        }),
                    )
                elif column.data_type == Column.ColumnType.URL:
                    self.fields[field_name] = forms.URLField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.URLInput(attrs={
                            'class': 'form-control',
                            'placeholder': 'Введите ссылку'
                        }),
                    )
                elif column.data_type == Column.ColumnType.FILE:
                    self.fields[field_name] = forms.FileField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=FileInputWithPreview(attrs={
                            'class': 'form-control',
                            'placeholder': 'Загрузите файл'
                        }),
                    )
                elif column.data_type == Column.ColumnType.FLOAT:
                    self.fields[field_name] = forms.FloatField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'step': '0.01',
                            'placeholder': 'Введите число с плавающей точкой'
                        }),
                    )
                elif column.data_type == Column.ColumnType.BOOLEAN:
                    self.fields[field_name] = forms.BooleanField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.CheckboxInput(attrs={
                            'class': 'form-check-input'
                        })
                    )
                elif column.data_type == Column.ColumnType.DATE:
                    self.fields[field_name] = forms.DateField(
                        label=column.name,
                        required=required,
                        initial=str(initial_value),
                        widget=forms.DateInput(attrs={
                            'type': 'date',
                            'class': 'form-control',
                            'placeholder': 'Выберите дату'
                        }),
                    )
                else:  # TEXT по умолчанию
                    self.fields[field_name] = forms.CharField(
                        label=column.name,
                        required=required,
                        initial=initial_value,
                        widget=forms.TextInput(attrs={
                            'class': 'form-control',
                            'placeholder': 'Введите текст'
                        }),
                    )


class FileInputWithPreview(forms.FileInput):
    def render(self, name, value, attrs=None, renderer=None):
        output = []
        if value and hasattr(value, 'url'):
            output.append(
                f'<div class="current-file">'
                f'<span>Текущий файл: </span>'
                f'<a href="{value.url}" target="_blank">{value.name}</a>'
                f'<label class="delete-file-checkbox">'
                f'<input type="checkbox" name="{name}-clear"> Удалить файл'
                f'</label>'
                f'</div>'
            )
        output.append(super().render(name, value, attrs, renderer))
        return mark_safe('\n'.join(output))
