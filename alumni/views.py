from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import AlumniRegistrationForm

def registration_view(request):
    if request.method == 'POST':
        form = AlumniRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful! See you at the reunion.')
            return redirect('alumni_registration')
    else:
        form = AlumniRegistrationForm()

    return render(request, 'alumni/registration.html', {'form': form})

from django.db.models import Count
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from .models import AlumniRegistration

def alumni_list_view(request):
    stats = AlumniRegistration.objects.values('batch', 'course__name').annotate(count=Count('id')).order_by('batch', 'course__name')
    alumni_list = AlumniRegistration.objects.all().order_by('-created_at')
    return render(request, 'alumni/alumni_list.html', {'stats': stats, 'alumni_list': alumni_list})

def render_pdf_view(request):
    stats = (
        AlumniRegistration.objects
        .values('batch', 'course__name')
        .annotate(count=Count('id'))
        .order_by('batch', 'course__name')
    )

    template_path = 'alumni/alumni_report_pdf.html'
    context = {'stats': stats}

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="alumni_report.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('PDF generation failed')

    return response


def home_view(request):
    return render(request, 'alumni/home.html')

def delete_alumni(request, pk):
    if request.method == 'POST':
        alumni = get_object_or_404(AlumniRegistration, pk=pk)
        alumni.delete()
        messages.success(request, 'Alumni record deleted successfully.')
    return redirect('alumni_list')
