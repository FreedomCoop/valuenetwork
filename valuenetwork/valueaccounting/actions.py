import csv
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

def export_as_csv(modeladmin, request, queryset):
    """
    Generic csv export admin action.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    opts = modeladmin.model._meta
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % str(opts).replace('.', '_')
    writer = csv.writer(response)
    field_names = [field.name for field in opts.fields]
    # Write a first row with header information
    writer.writerow(field_names)
    # Write data rows
    for obj in queryset:
        #writer.writerow([str(getattr(obj, field)).encode('latin-1', 'replace') for field in field_names])
        row = []
        for field in field_names:
            x = getattr(obj, field)
            try:
                x = x.encode('latin-1', 'replace')
            except AttributeError:
                pass
            row.append(x)
        writer.writerow(row)
                
    return response
export_as_csv.short_description = "Export selected objects as csv file"
