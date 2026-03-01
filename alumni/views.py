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
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
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

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="alumni_report.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("Alumni Registration Report", styles['Title']))
    elements.append(Spacer(1, 12))

    # Table Data
    data = [['Batch (Year)', 'Course', 'Number of Registrations']]
    for stat in stats:
        data.append([
            str(stat['batch']), 
            str(stat['course__name']), 
            str(stat['count'])
        ])

    # Table styling
    t = Table(data, colWidths=[100, 200, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(t)
    doc.build(elements)

    return response


def home_view(request):
    return render(request, 'alumni/home.html')

def delete_alumni(request, pk):
    if request.method == 'POST':
        alumni = get_object_or_404(AlumniRegistration, pk=pk)
        alumni.delete()
        messages.success(request, 'Alumni record deleted successfully.')
    return redirect('alumni_list')
