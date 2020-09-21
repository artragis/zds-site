from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    try:
        return dictionary.get(key)
    except:
        return []
