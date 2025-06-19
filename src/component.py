'''
Template Component main class.

'''
import datetime
import logging
import os
import sys
from pathlib import Path
from typing import List

from kbc.env_handler import KBCEnvHandler
from kbc.result import ResultWriter, KBCTableDef

from result import OrderWriter, ProductsWriter, CustomersWriter
from shopify_cli import ShopifyClient

# configuration variables
KEY_API_TOKEN = '#api_token'

KEY_SINCE_DATE = 'date_since'
KEY_TO_DATE = 'date_to'
KEY_INCREMENTAL_OUTPUT = 'incremental_output'
KEY_FETCH_PARAMETER = 'fetch_parameter'
KEY_LOADING_OPTIONS = 'loading_options'

KEY_ENDPOINTS = 'endpoints'
KEY_ORDERS = 'orders'
KEY_PAYMENTS_TRANSACTIONS = 'payments_transactions'
KEY_PRODUCTS = 'products'
KEY_PRODUCTS_ARCHIVED = 'products_archived'
KEY_PRODUCTS_DRAFTS = 'products_drafts'
KEY_CUSTOMERS = 'customers'
KEY_EVENTS = 'events'
KEY_INVENTORY = 'inventory'

KEY_SHOP = 'shop'

# #### Keep for debug
KEY_DEBUG = 'debug'

# list of mandatory parameters => if some is missing, component will fail with readable message on initialization.
MANDATORY_PARS = [KEY_API_TOKEN, KEY_SHOP, KEY_LOADING_OPTIONS, KEY_ENDPOINTS]
MANDATORY_IMAGE_PARS = []


class UserException(Exception):
    pass


class Component(KBCEnvHandler):

    def __init__(self, debug=False):
        # for easier local project setup
        default_data_dir = Path(__file__).resolve().parent.parent.joinpath('data').as_posix() \
            if not os.environ.get('KBC_DATADIR') else None

        KBCEnvHandler.__init__(self, MANDATORY_PARS, log_level=logging.DEBUG if debug else logging.INFO,
                               data_path=default_data_dir)

        self.last_state = self.get_state_file() or {}

        # override debug from config
        if self.cfg_params.get(KEY_DEBUG):
            debug = True
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger('pyactiveresource.connection').setLevel(
                logging.WARNING)  # avoid detail logs from the library
            logging.getLogger('backoff').setLevel(
                logging.WARNING)  # avoid detail logs from the library
        logging.info('Loading configuration...')

        try:
            # validation of mandatory parameters. Produces ValueError
            self.validate_config(MANDATORY_PARS)
            self.validate_image_parameters(MANDATORY_IMAGE_PARS)
        except ValueError as e:
            logging.exception(e)
            exit(1)

        self.validate_api_token(self.cfg_params[KEY_API_TOKEN])

        try:
            self.client = ShopifyClient(self.cfg_params[KEY_SHOP], self.cfg_params[KEY_API_TOKEN],
                                        self.cfg_params.get('api_version', '2022-10'))
        except Exception as e:
            raise UserException(f"Error while creating Shopify client: {e}") from e

        self.extraction_time = datetime.datetime.now().isoformat()

        # shared customers writer
        self._customer_writer = CustomersWriter(self.tables_out_path,
                                                'customer',
                                                extraction_time=self.extraction_time,
                                                file_headers=self.last_state)
        self._metafields_writer = ResultWriter(self.tables_out_path,
                                               KBCTableDef(name='metafields',
                                                           pk=['id'],
                                                           columns=self.last_state.get(
                                                               'metafields.csv', []),
                                                           destination=''),
                                               flatten_objects=True, child_separator='__', fix_headers=True)

    def run(self):
        '''
        Main execution code
        '''
        params = self.cfg_params  # noqa

        fetch_parameter = params[KEY_LOADING_OPTIONS].get(KEY_FETCH_PARAMETER) or 'updated_at'
        since = params[KEY_LOADING_OPTIONS].get(KEY_SINCE_DATE) or '2005-01-01'
        until = params[KEY_LOADING_OPTIONS].get(KEY_TO_DATE) or 'now'

        start_date, end_date = self.get_date_period_converted(since, until)
        results = []
        endpoints = params[KEY_ENDPOINTS]

        if endpoints.get(KEY_ORDERS):
            logging.info(f'Getting orders since {start_date} to {end_date}')
            results.extend(self.download_orders(fetch_parameter, start_date, end_date, self.last_state))

        if endpoints.get(KEY_PRODUCTS):
            logging.info(f'Getting products since {start_date} to {end_date}')
            results.extend(self.download_products(fetch_parameter, start_date, end_date, self.last_state))

        if endpoints.get(KEY_PAYMENTS_TRANSACTIONS):
            logging.info('Getting payments transactions')
            results.extend(self.download_payments_transactions())

        if endpoints.get(KEY_CUSTOMERS):
            # special case, results collected at the end
            logging.info(f'Getting customers since {start_date} to {end_date}')
            self.download_customers(fetch_parameter, start_date, end_date)

        if endpoints.get(KEY_EVENTS) and len(endpoints[KEY_EVENTS]) > 0:
            logging.info(f'Getting events since {start_date} to {end_date}')
            results.extend(self.download_events(endpoints[KEY_EVENTS][0], fetch_parameter, start_date, end_date))

        # collect customers
        self._customer_writer.close()
        results.extend(self._customer_writer.collect_results())

        # collect metafields
        self._metafields_writer.close()
        results.extend(self._metafields_writer.collect_results())

        # update column names in statefile
        for r in results:
            file_name = os.path.basename(r.full_path)
            self.last_state[file_name] = r.table_def.columns
        self.write_state_file(self.last_state)
        incremental = params[KEY_LOADING_OPTIONS].get(KEY_INCREMENTAL_OUTPUT, False)
        self.create_manifests(results, incremental=incremental)

    def get_product_status(self):
        status = ['active']
        if KEY_PRODUCTS_ARCHIVED in self.cfg_params[KEY_ENDPOINTS]:
            if self.cfg_params[KEY_ENDPOINTS][KEY_PRODUCTS_ARCHIVED]:
                status.append('archived')
        if KEY_PRODUCTS_DRAFTS in self.cfg_params[KEY_ENDPOINTS]:
            if self.cfg_params[KEY_ENDPOINTS][KEY_PRODUCTS_ARCHIVED]:
                status.append('draft')
        return ','.join(status)

    def download_orders(self, fetch_field, start_date, end_date, file_headers):
        with OrderWriter(self.tables_out_path, 'order', extraction_time=self.extraction_time,
                         customers_writer=self._customer_writer,
                         file_headers=file_headers) as writer_orders, \
                ResultWriter(self.tables_out_path,
                             KBCTableDef(name='transactions',
                                         pk=['order_id', 'id'],
                                         columns=file_headers.get('transactions.csv', []),
                                         destination=''), fix_headers=True,
                             flatten_objects=False, child_separator='__') as writer_order_transactions:
            orders_processed = 0
            for o in self.client.get_orders(fetch_field, start_date, end_date):
                writer_orders.write(o)
                orders_processed += 1

                if self.cfg_params[KEY_ENDPOINTS].get('transactions'):
                    self.download_order_transactions(writer_order_transactions, o['id'])

                if orders_processed % 1000 == 0:
                    logging.info(f"Downloading records: {orders_processed} - {orders_processed + 1000}")

        results = writer_orders.collect_results()
        results.extend(writer_order_transactions.collect_results())

        return results

    def download_payments_transactions(self):
        with ResultWriter(self.tables_out_path,
                          KBCTableDef(name='payments_transactions',
                                      pk=['id'],
                                      columns=[],
                                      destination=''),
                          fix_headers=True,
                          flatten_objects=False,
                          child_separator='__') as writer_payments_transactions:
            payment_transactions_processed = 0
            for o in self.client.get_payments_transactions():
                writer_payments_transactions.write(o)
                payment_transactions_processed += 1

                if payment_transactions_processed % 1000 == 0:
                    logging.info(f"Downloading records: {payment_transactions_processed} "
                                 f"- {payment_transactions_processed + 1000}")

        return writer_payments_transactions.collect_results()

    def download_products(self, fetch_field, start_date, end_date, file_headers):
        inventory_writer = ResultWriter(self.tables_out_path,
                                        KBCTableDef(name='inventory_items', pk=['id'],
                                                    columns=[],
                                                    destination=''),
                                        flatten_objects=True, child_separator='__')
        inventory_level_writer = ResultWriter(self.tables_out_path,
                                              KBCTableDef(name='inventory_levels',
                                                          pk=['inventory_item_id', 'location_id'],
                                                          columns=[],
                                                          destination=''),
                                              fix_headers=True,
                                              flatten_objects=True, child_separator='__')
        if self.cfg_params[KEY_ENDPOINTS].get(KEY_INVENTORY):
            logging.info('Getting inventory levels and locations for products')

        with ProductsWriter(self.tables_out_path, 'product',
                            extraction_time=self.extraction_time,
                            file_headers=file_headers) as writer:
            for o in self.client.get_products(fetch_field, start_date, end_date, self.get_product_status()):
                variants = [p['variants'] for p in o]
                inventory_ids = [str(v['inventory_item_id']) for sublist in variants for v in sublist]
                writer.write_all(o)
                if o and self.cfg_params[KEY_ENDPOINTS].get(KEY_INVENTORY):
                    self.download_product_inventory(inventory_writer, inventory_ids)
                    self.download_product_inventory_levels(inventory_level_writer, inventory_ids)

                if self.cfg_params[KEY_ENDPOINTS].get('product_metafields'):
                    self.download_metafields('products', [p['id'] for p in o])

                if self.cfg_params[KEY_ENDPOINTS].get('variant_metafields'):
                    self.download_metafields('variants', [v['id'] for sublist in variants for v in sublist])

        inventory_writer.close()
        inventory_level_writer.close()

        results = writer.collect_results()
        results.extend(inventory_level_writer.collect_results())
        results.extend(inventory_writer.collect_results())
        results.extend(self.download_locations())

        return results

    def download_locations(self):
        with ResultWriter(self.tables_out_path,
                          KBCTableDef(name='locations', pk=['id'],
                                      columns=[],
                                      destination=''),
                          flatten_objects=True, child_separator='__') as writer:
            for item in self.client.get_locations():
                writer.write(item)

        return writer.collect_results()

    def download_metafields(self, object_type: str, owner_ids: List[str]):
        for oid in owner_ids:
            for metafield in self.client.get_metafields(object_type, oid):
                self._metafields_writer.write(metafield)

    def download_product_inventory(self, writer, inventory_ids):
        for chunk in self._split_array_to_chunks(inventory_ids, 49):
            for item in self.client.get_inventory_items(chunk):
                writer.write(item)

    def download_product_inventory_levels(self, writer, inventory_ids):
        for chunk in self._split_array_to_chunks(inventory_ids, 49):
            for item in self.client.get_inventory_item_levels(chunk):
                writer.write(item)

    def download_customers(self, fetch_field, start_date, end_date):
        for o in self.client.get_customers(fetch_field, start_date, end_date):
            self._customer_writer.write(o)

    def download_order_transactions(self, writer, order_id):
        for transaction in self.client.get_order_transactions(order_id):
            writer.write(transaction)

    def download_events(self, param, fetch_field, start_date, end_date):
        headers = [
            "id",
            "subject_id",
            "created_at",
            "subject_type",
            "verb",
            "arguments",
            "body",
            "message",
            "author",
            "description",
            "path"
        ]
        with ResultWriter(self.tables_out_path,
                          KBCTableDef(name='events', pk=['id'],
                                      columns=headers,
                                      destination=''),
                          fix_headers=True, flatten_objects=True, child_separator='__') as writer:

            # iterate over types

            types = self.parse_comma_separated_values(param['types'])
            filters = param['filters']
            if not types:
                types = [None]
            for t in types:
                for o in self.client.get_events(fetch_field, start_date, end_date, filter_resource=filters,
                                                event_type=t):
                    writer.write(o)

        results = writer.collect_results()
        return results

    @staticmethod
    def _split_array_to_chunks(items: list, chunk_size: int):
        """
        Helper method to split items into chunks of specified size
        Args:
            items:
            chunk_size:

        Returns:

        """
        buffered = 0
        buffer = []
        for p in items:
            buffered += 1
            buffer.append(p)
            if buffered >= chunk_size:
                results = buffer.copy()
                buffer = []
                yield results
        if buffer:
            yield buffer

    @staticmethod
    def parse_comma_separated_values(param) -> List[str]:
        cols = []
        if param:
            cols = [p.strip() for p in param.split(",")]
        return cols

    @staticmethod
    def validate_api_token(token):
        try:
            for letter in token:
                letter.encode('latin-1')
        except UnicodeEncodeError:
            raise UserException("Password/API token that was entered is not valid, please re-enter it."
                                " Make sure to follow the custom app creation in the description of the component")


"""
        Main entrypoint
"""
if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_arg = sys.argv[1]
    else:
        debug_arg = False
    try:
        comp = Component(debug_arg)
        comp.run()
    except Exception as exc:
        logging.exception(exc)
        exit(1)
