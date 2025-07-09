from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Table, Column, Cell, Filial, TablePermission, TableFilialPermission


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ['title']


class ColumnForm(forms.ModelForm):
    class Meta:
        model = Column
        fields = ['name', 'data_type', 'is_required']
        widgets = {
            'data_type': forms.Select(choices=Column.ColumnType.choices),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    labels = {
        'is_required': 'Обязательное поле'
    }


class TablePermissionForm(forms.ModelForm):
    class Meta:
        model = TablePermission
        fields = ['permission_type']
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


class PermissionUserForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'userSelect'
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
    def __init__(self, *args, columns, **kwargs):
        self.table = kwargs.pop('table', None)
        super().__init__(*args, **kwargs)

        if self.table:
            for column in columns:
                field_name = f'col_{column.id}'
                initial_value = Cell.get_default_value(column.data_type)

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

    def clean(self):
        cleaned_data = super().clean()

        for field_name, value in cleaned_data.items():
            column_id = int(field_name.split('_')[1])
            column = Column.objects.get(id=column_id)
            value_type = type(value)

            if column.is_required and value in [None, '']:
                self.add_error(field_name, ValidationError(
                    'Это поле обязательно для заполнения',
                    code='required'
                ))

            if column.data_type == Column.ColumnType.FLOAT:
                if value_type is not float:
                    self.add_error(column, ValidationError('Invalid value', code='Должно быть float числом'))
            elif column.data_type == Column.ColumnType.INTEGER:
                if value_type is not int:
                    self.add_error(column, ValidationError('Invalid value', code='Должно быть int числом'))
            elif column.data_type == Column.ColumnType.BOOLEAN:
                if value_type is not bool:
                    self.add_error(column, ValidationError('Invalid value', code='Должно быть true/false'))
            elif column.data_type == Column.ColumnType.DATE:
                pass  # Пока не реализовано
