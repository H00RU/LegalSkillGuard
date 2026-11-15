"""Public calendar arithmetic; contains no legal threshold or entitlement."""
from datetime import date


def _date(value):
    if not isinstance(value,str):
        raise ValueError('An explicit ISO calendar date is required')
    parsed=date.fromisoformat(value)
    if parsed.isoformat()!=value:
        raise ValueError('Calendar dates use canonical YYYY-MM-DD')
    return parsed


def year_days(year):
    if type(year) is not int:
        raise ValueError('An explicit integer query year is required')
    return (date(year,12,31)-date(year,1,1)).days+1


def inclusive_year_overlap_days(start,end,year):
    first,last=_date(start),_date(end)
    year_days(year)
    if last<first:
        raise ValueError('The observed interval ends before it begins')
    lower=max(first,date(year,1,1));upper=min(last,date(year,12,31))
    return max(0,(upper-lower).days+1)


def calendar_year(value):
    return _date(value).year


def elapsed_year_overlap_days(start,end,year):
    """Timestamp-style duration between clipped midnight dates (not inclusive)."""
    first,last=_date(start),_date(end)
    year_days(year)
    if last<first:
        raise ValueError('The observed interval ends before it begins')
    lower=max(first,date(year,1,1));upper=min(last,date(year,12,31))
    return max(0,(upper-lower).days)
