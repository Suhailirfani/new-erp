from django.db import models

class Candidate(models.Model):
    BOARD_CHOICES = [
        ('SK SVB', 'Samastha Kerala Sunni Vidyabhyasa Board'),
        ('SK IMVB', 'Samastha Kerala Islam Matha Vidyabhyasa Board'),
    ]
    
    GRADE_CHOICES = [
        ('TOPPER', 'Topper'),
        ('TOP_PLUS', 'Top Plus'),
        ('DISTINCTION', 'Distinction'),
    ]
    
    name = models.CharField(max_length=255)
    father_name = models.CharField(max_length=255)
    mobile_number = models.CharField(max_length=15)
    madrasa_and_place = models.CharField(max_length=255)
    student_class = models.CharField(max_length=50) # 'class' is a reserved keyword in Python
    board = models.CharField(max_length=10, choices=BOARD_CHOICES)
    grade = models.CharField(max_length=15, choices=GRADE_CHOICES)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class AwazeGCampCandidate(models.Model):
    name = models.CharField(max_length=255)
    father_name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15)
    student_class = models.CharField(max_length=50)
    age = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CampMessage(models.Model):
    message_text = models.TextField(default="To: {name},\n\nതാഴപ്ര മർക്കസ് ഹാദിയ വിമൻസ് കോളേജ് സംഘടിപ്പിക്കുന്ന Awaze G-Camp-ലേക്ക് താങ്കൾ വിജയകരമായി രജിസ്റ്റർ ചെയ്തിരിക്കുന്നു. പുതിയ അനുഭവങ്ങളും അറിവുകളും തേടിയുള്ള ഈ മൂന്ന് ദിനങ്ങളിലേക്ക് നിങ്ങളെ ഞങ്ങൾ സ്വാഗതം ചെയ്യുന്നു.\n\n• ക്യാമ്പ് വിവരങ്ങൾ:\n• തീയതി: 2026 ഏപ്രിൽ 25, 26, 27\n• സമയം: ഏപ്രിൽ 25 ശനി രാവിലെ 9:00 AM മുതൽ ഏപ്രിൽ 27 തിങ്കൾ വൈകിട്ട് 4:00 PM വരെ.\n• സ്ഥലം: മർക്കസ് ഹാദിയ വിമൻസ് കോളേജ്, താഴപ്ര.\n• Location: https://maps.app.goo.gl/4w6ibRWRbbSzqCwt5\n\n• ഫീസ് വിവരങ്ങൾ:\n• ക്യാമ്പ് ഫീ: 2000 രൂപ.\n• Early Bird Offer: ഏപ്രിൽ 10-ന് മുൻപ് ഫീസ് അടക്കുന്നവർക്ക് 1600 രൂപ മാത്രം.\n\n• ഫീസ് അടക്കേണ്ട വിധം:\n• 95443 41515 എന്ന നമ്പറിലേക്ക് Gpay ചെയ്ത ശേഷം സ്ക്രീൻഷോട്ട് ഇതേ നമ്പറിലേക്ക് വാട്സ്ആപ്പ് ചെയ്യുക. പണമടച്ച് സ്ക്രീൻഷോട്ട് അയക്കുന്നതോടെ നിങ്ങളുടെ സീറ്റ് കൺഫേം ആകുന്നതാണ്.\n\n• ശ്രദ്ധിക്കുക:\n• ക്യാമ്പിന് വരുമ്പോൾ ആവശ്യമായ വസ്ത്രങ്ങൾ, വ്യക്തിപരമായ ആവശ്യത്തിനുള്ള സാധനങ്ങൾ എന്നിവ കരുതുക.\n\nകൂടുതൽ വിവരങ്ങൾക്ക്: +91 99473 64747\n\nക്യാമ്പിൽ വെച്ച് കാണാം!\n\nസ്നേഹപൂർവ്വം,\nടീം AWAZE\nമർക്കസ് ഹാദിയ താഴപ്ര")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Camp WhatsApp Message"
