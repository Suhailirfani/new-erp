from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key (supports string & int keys)"""
    if dictionary is None or not isinstance(dictionary, dict):
        return None
    if key in dictionary:
        return dictionary[key]
    str_key = str(key)
    if str_key in dictionary:
        return dictionary[str_key]
    return None


@register.filter
def slot_key(day_key, period_id):
    """Combines day_key and period_id into a dictionary lookup key, e.g. 'monday_1'"""
    return f"{day_key}_{period_id}"
