import backoff
import datetime
import functools
import logging
import math
import pyactiveresource
import pyactiveresource.formats
import shopify
import sys
from typing import Type

# ##################  Taken from Sopify Singer-Tap

RESULTS_PER_PAGE = 175

# We've observed 500 errors returned if this is too large (30 days was too
# large for a customer)
DATE_WINDOW_SIZE = 1

# We will retry a 500 error a maximum of 5 times before giving up
MAX_RETRIES = 5


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
    exc_info = sys.exc_info()
    resp = exc_info[1].response
    # Retry-After is an undocumented header. But honoring
    # it was proven to work in our spikes.
    # It's been observed to come through as lowercase, so fallback if not present
    sleep_time_str = resp.headers.get('Retry-After', resp.headers.get('retry-after'))
    yield math.floor(float(sleep_time_str))


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


class Error(Exception):
    """Base exception for the API interaction module"""


class OutOfOrderIdsError(Error):
    """Raised if our expectation of ordering by ID is violated"""


class ShopifyClient:

    def __init__(self, shop: str, access_token: str, api_version: str = '2020-10'):
        shop_url = f'{shop}.myshopify.com'
        self.session = shopify.Session(shop_url, api_version, access_token)
        shopify.ShopifyResource.activate_session(self.session)

    def get_orders(self, updated_at_min: datetime.datetime = None,
                   updated_at_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                   status='any', fields=None, results_per_page=RESULTS_PER_PAGE):

        additional_params = {}
        if fields:
            additional_params['fields'] = fields

        return self.get_objects_paginated(shopify.Order,
                                          updated_at_min=updated_at_min,
                                          updated_at_max=updated_at_max,
                                          results_per_page=results_per_page,
                                          status=status,
                                          **additional_params)

    def get_products(self, updated_at_min: datetime.datetime = None,
                     updated_at_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                     status='active', fields=None, results_per_page=RESULTS_PER_PAGE):

        additional_params = {}
        if fields:
            additional_params['fields'] = fields

        return self.get_objects_paginated(shopify.Product,
                                          updated_at_min=updated_at_min,
                                          updated_at_max=updated_at_max,
                                          results_per_page=results_per_page,
                                          status=status,
                                          **additional_params)

    @error_handling
    def call_api_all_pages(self, shopify_object, query_params):
        # this makes the PaginatedCollection iterator actually fetch all pages automatically
        query_params['no_iter_next'] = False
        return shopify_object.find(**query_params)

    def get_objects_paginated(self, shopify_object: Type[shopify.ShopifyResource],
                              updated_at_min: datetime.datetime = None,
                              updated_at_max: datetime.datetime = datetime.datetime.now().replace(microsecond=0),
                              date_window_size: int = DATE_WINDOW_SIZE,
                              results_per_page=RESULTS_PER_PAGE, **kwargs):
        """
        Get all objects and paginate per date. The pagination is also limited by the ``date_window_size`` parameter,
        that prevents overloading the API and getting too many 500s.
        Args:
            shopify_object (Type[shopify.ShopifyResource]): Shopify object to retrieve.
            updated_at_min (datetime): Min date
            updated_at_max (datetime): Max date
            date_window_size: Size of the window to get in each request (days
            results_per_page:
            **kwargs:

        Yields:
            Array of objects as dict

        """
        updated_at_min = updated_at_min.replace(microsecond=0)

        stop_time = updated_at_max

        # Page through till the end of the result set
        # NOTE: "Artificial" pagination done in Singer Tap, keeping it since it apparently causes 500 errors
        # when requesting full period. Eg. paging per window_size (1day)
        # however it was simplified to leverage shopify native pagination function
        while updated_at_min < stop_time:

            # ## Original Singer Tap comment
            # It's important that `updated_at_min` has microseconds
            # truncated. Why has been lost to the mists of time but we
            # think it has something to do with how the API treats
            # microseconds on its date windows. Maybe it's possible to
            # drop data due to rounding errors or something like that?
            updated_at_max = updated_at_min + datetime.timedelta(days=date_window_size)
            if updated_at_max > stop_time:
                updated_at_max = stop_time

            query_params = {**{
                "updated_at_min": updated_at_min.isoformat(),
                "updated_at_max": updated_at_max.isoformat(),
                "limit": results_per_page
            }, **kwargs}

            result_page = self.call_api_all_pages(shopify_object, query_params)

            # iterate through pages (the iterator does this on the background
            for obj in result_page:
                yield obj.to_dict()

            updated_at_min = updated_at_max
