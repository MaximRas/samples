from functools import wraps
import time
import logging

log = logging.getLogger('tools.retry')


def retry(
        exception_to_check,
        tries: int = 2,
        delay: float = 1.,
):
    def deco_retry(func):
        @wraps(func)
        def func_retry(*args, **kwargs):
            last_exception = None
            for try_number in range(tries):
                try:
                    return func(*args, **kwargs)
                except exception_to_check as exc:
                    last_exception = exc
                    log.warning(f"{exc.__class__.__name__}: {exc} occured in {func.__name__}. used attempts: {try_number+1} of {tries}")
                    time.sleep(delay)
            # TODO: print exception message
            raise exception_to_check from last_exception
        return func_retry

    return deco_retry
