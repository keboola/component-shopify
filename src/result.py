from kbc.result import ResultWriter, KBCTableDef

EXTRACTION_TIME = 'extraction_time'

KEY_ROW_NR = 'row_nr'


class LineItemWriter(ResultWriter):
    def __init__(self, result_dir_path, extraction_time, additional_pk: list = None, prefix='', file_headers=None):
        pk = ['id']
        if additional_pk:
            pk.extend(additional_pk)
        file_name = f'{prefix}line_item'
        ResultWriter.__init__(self, result_dir_path,
                              KBCTableDef(name=file_name, pk=pk, columns=file_headers.get(f'{file_name}.csv', []),
                                          destination=''),
                              fix_headers=True, flatten_objects=True, child_separator='__')
        self.extraction_time = extraction_time

        self.result_dir_path = result_dir_path

        # discount_allocations writer
        self.discount_allocations_writer = ResultWriter(result_dir_path,
                                                        KBCTableDef(name=f'{prefix}line_item_discount_allocations',
                                                                    pk=[KEY_ROW_NR, 'line_item_id'],
                                                                    columns=file_headers.get(
                                                                        f'{prefix}line_item_discount_allocations.csv',
                                                                        []),
                                                                    destination=''),
                                                        flatten_objects=True,
                                                        fix_headers=True,
                                                        child_separator='__')
        # tax_lines writer
        self.tax_lines_writer = ResultWriter(result_dir_path,
                                             KBCTableDef(name=f'{prefix}line_item_tax_lines',
                                                         pk=[KEY_ROW_NR, 'line_item_id'],
                                                         columns=file_headers.get(
                                                             f'{prefix}line_item_tax_lines.csv',
                                                             []),
                                                         destination=''),
                                             flatten_objects=True,
                                             fix_headers=True,
                                             child_separator='__')

    def write(self, data, file_name=None, user_values=None, object_from_arrays=False, write_header=True):
        # flatten obj
        line_item_id = data['id']

        for idx, el in enumerate(data.pop('discount_allocations', [])):
            el[KEY_ROW_NR] = idx
            self.discount_allocations_writer.write(el, user_values={"line_item_id": line_item_id,
                                                                    EXTRACTION_TIME: self.extraction_time})

        for idx, el in enumerate(data.pop('tax_lines', [])):
            el[KEY_ROW_NR] = idx
            self.tax_lines_writer.write(el, user_values={"line_item_id": line_item_id,
                                                         EXTRACTION_TIME: self.extraction_time})

        super().write(data, file_name, user_values, object_from_arrays, write_header)

    def collect_results(self):
        results = []
        results.extend(self.discount_allocations_writer.collect_results())
        results.extend(self.tax_lines_writer.collect_results())
        results.extend(super().collect_results())
        return results

    def close(self):
        self.discount_allocations_writer.close()
        self.tax_lines_writer.close()
        super().close()


class FulfillmentsWriter(ResultWriter):
    def __init__(self, result_dir_path, extraction_time, additional_pk: list = None, prefix='', file_headers=None):
        pk = ['id', 'order_id']
        if not additional_pk:
            pk.extend(additional_pk)

        ResultWriter.__init__(self, result_dir_path,
                              KBCTableDef(name=f'{prefix}fulfillments', pk=pk,
                                          columns=file_headers.get(
                                              f'{prefix}fulfillments.csv', []), destination=''),
                              fix_headers=True, flatten_objects=True, child_separator='__')
        self.extraction_time = extraction_time

        self.result_dir_path = result_dir_path
        # lineitems writer
        self.line_item_writer = LineItemWriter(result_dir_path, extraction_time, additional_pk=['fulfillment_id'],
                                               prefix='fulfillment_', file_headers=file_headers)

        # discount_allocations writer
        self.discount_allocations_writer = ResultWriter(result_dir_path,
                                                        KBCTableDef(name='fulfillment_discount_allocations',
                                                                    pk=[KEY_ROW_NR, 'fulfillment_id'],
                                                                    columns=file_headers.get(
                                                                        'fulfillment_discount_allocations.csv', []),
                                                                    destination=''),
                                                        flatten_objects=True,
                                                        fix_headers=True,
                                                        child_separator='__')
        # tax_lines writer
        self.tax_lines_writer = ResultWriter(result_dir_path,
                                             KBCTableDef(name='fulfillment_tax_lines',
                                                         pk=[KEY_ROW_NR, 'fulfillment_id'],
                                                         columns=file_headers.get(
                                                             'fulfillment_tax_lines.csv',
                                                             []),
                                                         destination=''),
                                             flatten_objects=True,
                                             fix_headers=True,
                                             child_separator='__')

    def write(self, data, file_name=None, user_values=None, object_from_arrays=False, write_header=True):
        # flatten obj
        fulfillment_id = data['id']
        line_items = data.pop('line_items', [])
        self.line_item_writer.write_all(line_items, user_values={"fulfillment_id": fulfillment_id,
                                                                 EXTRACTION_TIME: self.extraction_time})

        for idx, el in enumerate(data.pop('discount_applications', [])):
            el[KEY_ROW_NR] = idx
            self.discount_allocations_writer.write(el, user_values={"fulfillment_id": fulfillment_id,
                                                                    EXTRACTION_TIME: self.extraction_time})

        for idx, el in enumerate(data.pop('tax_lines', [])):
            el[KEY_ROW_NR] = idx
            self.tax_lines_writer.write(el, user_values={"fulfillment_id": fulfillment_id})

        super().write(data, file_name, user_values, object_from_arrays, write_header)

    def collect_results(self):
        results = []
        results.extend(self.line_item_writer.collect_results())
        results.extend(self.discount_allocations_writer.collect_results())
        results.extend(self.tax_lines_writer.collect_results())
        results.extend(super().collect_results())
        return results

    def close(self):
        self.line_item_writer.close()
        self.discount_allocations_writer.close()
        self.tax_lines_writer.close()
        super().close()


class OrderWriter(ResultWriter):

    def __init__(self, result_dir_path, result_name, extraction_time, customers_writer, file_headers=None):

        ResultWriter.__init__(self, result_dir_path,
                              KBCTableDef(name=result_name, pk=['id'],
                                          columns=file_headers.get('order.csv', []),
                                          destination=''),
                              fix_headers=True, flatten_objects=True, child_separator='__')
        self.extraction_time = extraction_time
        # custom user added col
        self.user_value_cols = ['extraction_time']
        self.result_dir_path = result_dir_path

        # lineitems writer
        self.line_item_writer = LineItemWriter(result_dir_path, extraction_time, additional_pk=['order_id'],
                                               file_headers=file_headers)

        # fulfillments writer
        self.fulfillments_writer = FulfillmentsWriter(result_dir_path, extraction_time, additional_pk=['order_id'],
                                                      prefix='order_',
                                                      file_headers=file_headers)

        # discount_applications writer
        self.discount_applications_writer = ResultWriter(result_dir_path,
                                                         KBCTableDef(name='order_discount_applications',
                                                                     pk=['order_id', KEY_ROW_NR],
                                                                     columns=file_headers.get(
                                                                         'order_discount_applications.csv', []),
                                                                     destination=''),
                                                         fix_headers=True,
                                                         flatten_objects=True,
                                                         child_separator='__')

        # discount_codes writer
        self.discount_codes_writer = ResultWriter(result_dir_path,
                                                  KBCTableDef(name='order_discount_codes',
                                                              pk=['order_id', KEY_ROW_NR],
                                                              columns=file_headers.get(
                                                                  'order_discount_codes.csv', []),
                                                              destination=''),
                                                  fix_headers=True,
                                                  flatten_objects=True,
                                                  child_separator='__')

        # tax_lines writer
        self.tax_lines_writer = ResultWriter(result_dir_path,
                                             KBCTableDef(name='order_tax_lines',
                                                         pk=['order_id', KEY_ROW_NR],
                                                         columns=file_headers.get(
                                                             'order_tax_lines.csv', []),
                                                         destination=''),
                                             fix_headers=True,
                                             flatten_objects=True,
                                             child_separator='__')

        # customer writer
        self.customer_writer = customers_writer

    def write(self, data, file_name=None, user_values=None, object_from_arrays=False, write_header=True):
        if not data:
            return

        # flatten obj
        order_id = data['id']
        line_items = data.pop('line_items')
        self.line_item_writer.write_all(line_items, user_values={"order_id": order_id,
                                                                 EXTRACTION_TIME: self.extraction_time})

        self.fulfillments_writer.write_all(data.pop('fulfillments', []), user_values={"order_id": order_id,
                                                                                      EXTRACTION_TIME:
                                                                                          self.extraction_time})

        for idx, el in enumerate(data.pop('discount_applications', [])):
            el[KEY_ROW_NR] = idx
            self.discount_applications_writer.write(el, user_values={"order_id": order_id,
                                                                     EXTRACTION_TIME: self.extraction_time})

        for idx, el in enumerate(data.pop('discount_codes', [])):
            el[KEY_ROW_NR] = idx
            self.discount_codes_writer.write(el, user_values={"order_id": order_id,
                                                              EXTRACTION_TIME: self.extraction_time})

        for idx, el in enumerate(data.pop('tax_lines', [])):
            el[KEY_ROW_NR] = idx
            self.tax_lines_writer.write(el, user_values={"order_id": order_id,
                                                         EXTRACTION_TIME: self.extraction_time})

        customer = data.pop('customer', {})
        if customer:
            data['customer_id'] = customer.get('id', '')
            self.customer_writer.write(customer)

        super().write(data, user_values=user_values)

    def collect_results(self):
        results = []
        results.extend(self.line_item_writer.collect_results())
        results.extend(self.fulfillments_writer.collect_results())
        results.extend(self.discount_applications_writer.collect_results())
        results.extend(self.tax_lines_writer.collect_results())
        results.extend(self.discount_codes_writer.collect_results())
        results.extend(super().collect_results())
        return results

    def close(self):
        self.line_item_writer.close()
        self.fulfillments_writer.close()
        self.discount_applications_writer.close()
        self.discount_codes_writer.close()
        self.tax_lines_writer.close()
        super().close()


# ###################### PRODUCTS

class ProductVariantWriter(ResultWriter):
    def __init__(self, result_dir_path, extraction_time, file_headers, additional_pk: list = None):
        pk = ['id', 'product_id']
        if additional_pk:
            pk.extend(additional_pk)

        ResultWriter.__init__(self, result_dir_path,
                              KBCTableDef(name='product_variant', pk=pk,
                                          columns=file_headers.get('product_variant.csv', []),
                                          destination=''),
                              fix_headers=True, flatten_objects=True, child_separator='__')
        self.extraction_time = extraction_time

        self.result_dir_path = result_dir_path

        # presentment_prices writer
        self.presentment_prices_writer = ResultWriter(result_dir_path,
                                                      KBCTableDef(name='product_variant_presentment_prices',
                                                                  pk=[KEY_ROW_NR, 'product_variant_id'],
                                                                  columns=file_headers.get(
                                                                      'product_variant_presentment_prices.csv', []),
                                                                  destination=''),
                                                      fix_headers=True, flatten_objects=True, child_separator='__')

    def write(self, data, file_name=None, user_values=None, object_from_arrays=False, write_header=True):
        # flatten obj
        product_variant_id = data['id']

        for idx, el in enumerate(data.pop('presentment_prices', [])):
            el[KEY_ROW_NR] = idx
            self.presentment_prices_writer.write(el, user_values={"product_variant_id": product_variant_id,
                                                                  EXTRACTION_TIME: self.extraction_time})

        super().write(data, file_name, user_values, object_from_arrays, write_header)

    def collect_results(self):
        results = []
        results.extend(self.presentment_prices_writer.collect_results())
        results.extend(super().collect_results())
        return results

    def close(self):
        self.presentment_prices_writer.close()
        super().close()


class ProductsWriter(ResultWriter):

    def __init__(self, result_dir_path, result_name, extraction_time, file_headers):
        ResultWriter.__init__(self, result_dir_path,
                              KBCTableDef(name=result_name, pk=['id'],
                                          columns=file_headers.get(
                                              f'{result_name}.csv', []),
                                          destination=''),
                              fix_headers=True, flatten_objects=True, child_separator='__')
        self.extraction_time = extraction_time
        # custom user added col
        self.user_value_cols = ['extraction_time']
        self.result_dir_path = result_dir_path

        # variants writer
        self.variants_writer = ProductVariantWriter(result_dir_path, extraction_time, file_headers)

        # options writer
        self.product_options_writer = ResultWriter(result_dir_path, KBCTableDef(name='product_options',
                                                                                pk=['id', 'product_id'],
                                                                                columns=file_headers.get(
                                                                                    'product_options.csv', []),
                                                                                destination=''),
                                                   fix_headers=True, flatten_objects=True, child_separator='__')
        # images writer
        self.product_images_writer = ResultWriter(result_dir_path, KBCTableDef(name='product_images',
                                                                               pk=['id', 'product_id'],
                                                                               columns=file_headers.get(
                                                                                   'product_images.csv', []),
                                                                               destination=''),
                                                  fix_headers=True, flatten_objects=True, child_separator='__')

    def write(self, data, file_name=None, user_values=None, object_from_arrays=False, write_header=True):
        product_id = data['id']
        self.product_images_writer.write_all(data.pop('images', []), user_values={'product_id': product_id,
                                                                                  EXTRACTION_TIME:
                                                                                      self.extraction_time})

        self.product_options_writer.write_all(data.pop('options', []), user_values={
            EXTRACTION_TIME: self.extraction_time})

        self.variants_writer.write_all(data.pop('variants', []), user_values={'product_id': product_id,
                                                                              EXTRACTION_TIME: self.extraction_time})

        super().write(data, user_values=user_values)

    def collect_results(self):
        results = []
        results.extend(self.product_options_writer.collect_results())
        results.extend(self.product_images_writer.collect_results())
        results.extend(self.variants_writer.collect_results())
        results.extend(super().collect_results())
        return results

    def close(self):
        self.product_options_writer.close()
        self.product_images_writer.close()
        self.variants_writer.close()
        super().close()


# ############ CUSTOMERS


class CustomersWriter(ResultWriter):
    """
    Sliced
    """

    def __init__(self, result_dir_path, result_name, extraction_time, file_headers):
        ResultWriter.__init__(self, result_dir_path,
                              KBCTableDef(name=result_name, pk=['id'],
                                          columns=file_headers.get(
                                              'customer.csv', []),
                                          destination=''),
                              fix_headers=True, flatten_objects=True, child_separator='__')
        self.extraction_time = extraction_time
        # custom user added col
        self.user_value_cols = ['extraction_time']

        # addresses writer
        self.address_writer = ResultWriter(result_dir_path, KBCTableDef(name='customer_addresses',
                                                                        pk=['id', 'customer_id'],
                                                                        columns=file_headers.get(
                                                                            'customer_addresses.csv', []),
                                                                        destination=''),
                                           fix_headers=True, flatten_objects=True, child_separator='__')

    def write(self, data, file_name=None, user_values=None, object_from_arrays=False, write_header=True):
        self.address_writer.write_all(data.pop('addresses', []), user_values={
            EXTRACTION_TIME: self.extraction_time})

        super().write(data, user_values=user_values, write_header=True)

    def collect_results(self):
        results = super().collect_results()
        results.extend(self.address_writer.collect_results())

        return results

    def close(self):
        self.address_writer.close()
        super().close()
