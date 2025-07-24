import tablib


class ImportFile:
    my_dataset = None

    def __init__(self, file):
        self.file = file
        self.my_dataset = tablib.Dataset()
        self.format = self.file.name.split('.')[-1]
        if self.format == 'xlsx':
            self.my_dataset.xlsx = self.file.read()
        elif self.format == 'xls':
            self.my_dataset.xls = self.file.read()
        elif self.format == 'csv':
            self.my_dataset.load(self.file.read().decode('utf-8-sig'), format='csv', delimiter=',')
        self.file.seek(0)
        self.file.close()

    def get_column_header(self):
        return self.my_dataset.headers

    def get_dataset_dict(self):
        return self.my_dataset.dict
