import datetime
import functools
import json
import logging
import math
import sys
import time
from enum import Enum
from typing import Type, List, Union

import backoff
import pyactiveresource
import pyactiveresource.formats
import shopify
from pyactiveresource.connection import ResourceNotFound, UnauthorizedAccess, ClientError
# ##################  Taken from Sopify Singer-Tap
from shopify import PaginatedIterator

RESULTS_PER_PAGE = 250

# We've observed 500 errors returned if this is too large (30 days was too
# large for a customer)
DATE_WINDOW_SIZE = 30

# We will retry a 500 error a maximum of 5 times before giving up
MAX_RETRIES = 5
BASE_SLEEP_TIME = 10


class ShopifyClientError(Exception):
    pass


def is_not_status_code_fn(status_code):
    def gen_fn(exc):
        if getattr(exc, 'code', None) and exc.code not in status_code:
            return True
        # Retry other errors up to the max
        return False

    return gen_fn


# Taken from Sopify Singer-Tap
def leaky_bucket_handler(details):
    logging.info("Received 429 -- sleeping for %s seconds",
                 details['wait'])


# Taken from Sopify Singer-Tap
def retry_handler(details):
    logging.info("Received 500 or retryable error -- Retry %s/%s",
                 details['tries'], MAX_RETRIES)


# ################  Taken from Sopify Singer-Tap
# pylint: disable=unused-argument
def retry_after_wait_gen(**kwargs):
    # This is called in an except block so we can retrieve the exception
    # and check it.

    # Advance past initial .send() call
    yield  # type: ignore[misc]

    exc_info = sys.exc_info()
    if exc_info[1] is None:
        yield 5
    elif exc_info[1]:
        resp = exc_info[1].response
        # Retry-After is an undocumented header. But honoring
        # it was proven to work in our spikes.
        # It's been observed to come through as lowercase, so fallback if not present
        sleep_time_str = resp.headers.get('Retry-After', resp.headers.get('retry-after', 0))
        yield math.floor(float(sleep_time_str) * 1.5)


def error_handling(fnc):
    @backoff.on_exception(backoff.expo,
                          (pyactiveresource.connection.ServerError,
                           pyactiveresource.formats.Error
                           ),
                          giveup=is_not_status_code_fn(range(500, 599)),
                          on_backoff=retry_handler,
                          max_tries=MAX_RETRIES)
    @backoff.on_exception(retry_after_wait_gen,
                          pyactiveresource.connection.ClientError,
                          giveup=is_not_status_code_fn([429]),
                          on_backoff=leaky_bucket_handler,
                          # No jitter as we want a constant value
                          jitter=None)
    @functools.wraps(fnc)
    def wrapper(*args, **kwargs):
        return fnc(*args, **kwargs)

    return wrapper


def response_error_handling(func):
    """Function, that handles response handling of HTTP requests.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ResourceNotFound as e:
            logging.error(e, exc_info=True)
            # Handle different error codes
            raise ShopifyClientError('The resource was not found. Please check your Shop ID!') from e
        except UnauthorizedAccess as e:
            error_msg = json.loads(e.response.body.decode('utf-8'))["errors"]
            raise ShopifyClientError(f'{error_msg}; Please check your credentials and app permissions!') from e
        except ClientError as e:
            error_msg = json.loads(e.response.body.decode('utf-8'))["errors"]
            raise ShopifyClientError(f'Request to {e.url} failed; Error: {error_msg}') from e

    return wrapper


class Error(Exception):
    """Base exception for the API interaction module"""


class OutOfOrderIdsError(Error):
    """Raised if our expectation of ordering by ID is violated"""


# data

class ShopifyResource(Enum):
    Article = "Article"
    Blog = "Blog"
    Collection = "Collection"
    Comment = "Comment"
    Order = "Order"
    Page = "Page"
    PriceRule = "PriceRule"
    Product = "Product"
    ApiPermission = "ApiPermission"

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))

    @classmethod
    def validate_fields(cls, fields: List[str]):
        errors = []
        for f in fields:
            if f not in cls.list():
                errors.append(f'"{f}" is not valid Shopify resource!')
        if errors:
            raise ValueError(
                ', '.join(errors) + f'\n Supported Resources are: [{cls.list()}]')


def _get_date_param_min(fetch_parameter: str):
    return f"{fetch_parameter}_min"


def _get_date_param_max(fetch_parameter: str):
    return f"{fetch_parameter}_max"


class ShopifyClient:

    def __init__(self, shop: str, access_token: str, api_version: str = '2022-10'):
        shop_url = f'{shop}.myshopify.com'
        self.session = shopify.Session(shop_url, api_version, access_token)
        self.wait_time_seconds = BASE_SLEEP_TIME
        shopify.ShopifyResource.activate_session(self.session)

    def get_orders(self, fetch_parameter: str, datetime_min: datetime.datetime = None,
                   datetime_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                   status='any', fields=None, results_per_page=RESULTS_PER_PAGE):
        """
        Get orders
        Args:
            fetch_parameter: Field to fetch
            datetime_min:
            datetime_max:
            status:
            fields:
            results_per_page:

        Returns: Generator object, list of orders

        """

        additional_params = {}
        if fields:
            additional_params['fields'] = fields

        return self.get_objects_paginated(shopify.Order,
                                          datetime_min=datetime_min,
                                          datetime_max=datetime_max,
                                          results_per_page=results_per_page,
                                          status=status,
                                          datetime_param_min=_get_date_param_min(fetch_parameter),
                                          datetime_param_max=_get_date_param_max(fetch_parameter),
                                          **additional_params)

    def get_metafields(self, resource: str, resource_id: str, results_per_page=RESULTS_PER_PAGE):

        additional_params = {'resource': resource, 'resource_id': resource_id}

        return self.get_objects_paginated_simple(shopify.Metafield, results_per_page,
                                                 **additional_params)

    def get_products(self, fetch_parameter: str, datetime_min: datetime.datetime = None,
                     datetime_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                     status='active', fields=None, results_per_page=RESULTS_PER_PAGE, return_chunk_size=90):
        """
        Get products
        Args:
            fetch_parameter: Field to fetch
            datetime_min:
            datetime_max:
            status:
            fields:
            results_per_page:
            return_chunk_size: Max size of the chunk of products to return

        Returns: Generator object, list of products

        """

        additional_params = {}
        if fields:
            additional_params['fields'] = fields

        buffered = 0
        buffer = []
        for p in self.get_objects_paginated(shopify.Product,
                                            datetime_min=datetime_min,
                                            datetime_max=datetime_max,
                                            results_per_page=results_per_page,
                                            status=status,
                                            datetime_param_min=_get_date_param_min(fetch_parameter),
                                            datetime_param_max=_get_date_param_max(fetch_parameter),
                                            **additional_params):
            buffered += 1
            buffer.append(p)
            if buffered >= return_chunk_size:
                results = buffer.copy()
                buffer = []
                yield results
        yield buffer

    def get_inventory_items(self, inventory_ids: list,
                            results_per_page=RESULTS_PER_PAGE):

        additional_params = {'ids': ','.join(inventory_ids)}
        return self.get_objects_paginated_simple(shopify.InventoryItem,
                                                 results_per_page=results_per_page,
                                                 **additional_params)

    def get_inventory_item_levels(self, inventory_ids: list,
                                  results_per_page=RESULTS_PER_PAGE):

        additional_params = {'inventory_item_ids': ','.join(inventory_ids)}
        return self.get_objects_paginated_simple(shopify.InventoryLevel,
                                                 results_per_page=results_per_page,
                                                 **additional_params)

    def get_locations(self, results_per_page=RESULTS_PER_PAGE):

        return self.get_objects_paginated_simple(shopify.Location,
                                                 results_per_page=results_per_page)

    def get_events(self, fetch_parameter: str, datetime_min: datetime.datetime = None,
                   datetime_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                   filter_resource: List[Union[ShopifyResource, str]] = None, event_type: str = None,
                   fields: List[str] = None,
                   results_per_page: int = RESULTS_PER_PAGE
                   ):

        """
        Retrieves a list of events.

        Args:
            fetch_parameter: Field to fetch
            datetime_min:
            datetime_max:
            filter_resource: Filter on certain events by the type of resource it produced. e.g.['Order','Product']
            event_type:
                eg 'confirmed', 'create', 'destroy' The type of event that occurred. Different resources generate
                different types of event. See the [docs](
                https://shopify.dev/docs/admin-api/rest/reference/events/event#resources-that-can-create-events) for
                a list of possible verbs.
            fields: List of fields to limit the response
            results_per_page:

        Returns:

        """

        additional_params = {}
        if filter_resource:
            if isinstance(filter_resource[0], ShopifyResource):
                filter_resource = [f.name for f in filter_resource]
            else:
                ShopifyResource.validate_fields(filter_resource)
            additional_params['filter'] = ','.join([f for f in filter_resource])

        if event_type:
            additional_params['verb'] = event_type

        if fields:
            additional_params['fields'] = fields

        return self.get_objects_paginated(shopify.Event,
                                          datetime_min=datetime_min,
                                          datetime_max=datetime_max,
                                          datetime_param_min='created_at_min',
                                          datetime_param_max='created_at_max',
                                          results_per_page=results_per_page,
                                          **additional_params)

    def get_customers(self, fetch_parameter: str, datetime_min: datetime.datetime = None,
                      datetime_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                      state=None, fields=None, results_per_page=RESULTS_PER_PAGE):
        additional_params = {}
        if fields:
            additional_params['fields'] = fields

        if state:
            additional_params['state'] = state

        return self.get_objects_paginated(shopify.Customer,
                                          datetime_min=datetime_min,
                                          datetime_max=datetime_max,
                                          results_per_page=results_per_page,
                                          datetime_param_min=_get_date_param_min(fetch_parameter),
                                          datetime_param_max=_get_date_param_max(fetch_parameter),
                                          **additional_params)

    @response_error_handling
    @error_handling
    def call_api_all_pages(self, shopify_object: Type[shopify.ShopifyResource], query_params):
        # this makes the PaginatedCollection iterator actually fetch all pages automatically
        query_params['no_iter_next'] = False
        return PaginatedIterator(shopify_object.find(**query_params))

    def get_objects_paginated_simple(self, shopify_object: Type[shopify.ShopifyResource],
                                     results_per_page=RESULTS_PER_PAGE,
                                     **kwargs):
        query_params = {**{
            "limit": results_per_page
        }, **kwargs}

        result_iterator = self.call_api_all_pages(shopify_object, query_params)

        # iterate through pages (the iterator does this on the background
        for collection in result_iterator:
            self.check_api_limit_use()
            for obj in collection:
                yield obj.to_dict()

    def get_objects_paginated(self, shopify_object: Type[shopify.ShopifyResource],
                              datetime_min: datetime.datetime = None,
                              datetime_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                              date_window_size: int = DATE_WINDOW_SIZE,
                              results_per_page=RESULTS_PER_PAGE,
                              datetime_param_min='updated_at_min',
                              datetime_param_max='updated_at_max',
                              **kwargs):
        """
        Get all objects and paginate per date. The pagination is also limited by the ``date_window_size`` parameter,
        that prevents overloading the API and getting too many 500s.
        Args:
            shopify_object (Type[shopify.ShopifyResource]): Shopify object to retrieve.
            datetime_min (datetime): Min date
            datetime_max (datetime): Max date
            date_window_size: Size of the window to get in each request days
            results_per_page:
            datetime_param_min: field date min parameter
            datetime_param_max: field date max parameter
            **kwargs:

        Yields:
            Array of objects as dict

        """
        datetime_min = datetime_min.replace(microsecond=0)

        stop_time = datetime_max

        # Page through till the end of the result set
        # NOTE: "Artificial" pagination done in Singer Tap, keeping it since it apparently causes 500 errors
        # when requesting full period. Eg. paging per window_size (1day)
        # however it was simplified to leverage shopify native pagination function
        while datetime_min < stop_time:

            # ## Original Singer Tap comment
            # It's important that `updated_at_min` has microseconds
            # truncated. Why has been lost to the mists of time but we
            # think it has something to do with how the API treats
            # microseconds on its date windows. Maybe it's possible to
            # drop data due to rounding errors or something like that?
            datetime_max = datetime_min + datetime.timedelta(days=date_window_size)
            if datetime_max > stop_time:
                datetime_max = stop_time

            query_params = {**{
                datetime_param_min: datetime_min.isoformat(),
                datetime_param_max: datetime_max.isoformat(),
                "limit": results_per_page
            }, **kwargs}

            result_iterator = self.call_api_all_pages(shopify_object, query_params)

            # iterate through pages (the iterator does this on the background
            for collection in result_iterator:
                self.check_api_limit_use()
                for obj in collection:
                    yield obj.to_dict()

            datetime_min = datetime_max

    def check_api_limit_use(self):
        used_credits, max_credits = self._try_get_credits()
        if int(used_credits) >= int(max_credits) - 1:
            time.sleep(self.wait_time_seconds)

    def _try_get_credits(self):
        """
        Sometimes shopify.Limits.api_credit_limit_param() fails because the X-Shopify-Shop-Api-Call-Limit is lower case
        Returns:

        """
        used_credits, max_credits = 1, 1
        lower_case_ratelimit = shopify.Limits.CREDIT_LIMIT_HEADER_PARAM.lower()
        header_found = False
        for key, value in shopify.Limits.response().headers.items():
            if key.lower() == lower_case_ratelimit:
                used_credits, max_credits = value.split("/")
                header_found = True
                break
        if not header_found:
            logging.warning(f"Header {lower_case_ratelimit} was not found in the response!")
        return used_credits, max_credits
