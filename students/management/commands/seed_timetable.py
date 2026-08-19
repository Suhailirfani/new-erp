import uuid
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from students.models import (
    Section, Grade, Division, Subject, PeriodTiming,
    TeacherSubjectAssignment, TimetableSlot, UserProfile, AcademicYear
)
from datetime import time

class Command(BaseCommand):
    help = "Seeds dummy data for testing the Timetable Management System"

    def handle(self, *args, **options):
        self.stdout.write("Seeding Timetable Dummy Data...")

        # 1. Active Academic Year
        active_year = AcademicYear.objects.filter(is_active=True).first()
        if not active_year:
            active_year = AcademicYear.objects.create(name="2026-2027", is_active=True)

        # 2. Period Timings (8 Periods + Tea Break + Lunch Break)
        pt_data = [
            ("Period 1", time(8, 30), time(9, 15), 1, False),
            ("Period 2", time(9, 15), time(10, 0), 2, False),
            ("Tea Break ☕", time(10, 0), time(10, 15), 3, True),
            ("Period 3", time(10, 15), time(11, 0), 4, False),
            ("Period 4", time(11, 0), time(11, 45), 5, False),
            ("Lunch Break 🍱", time(11, 45), time(12, 30), 6, True),
            ("Period 5", time(12, 30), time(13, 15), 7, False),
            ("Period 6", time(13, 15), time(14, 0), 8, False),
            ("Period 7", time(14, 0), time(14, 45), 9, False),
            ("Period 8", time(14, 45), time(15, 30), 10, False),
        ]
        
        timings_map = {}
        for name, st, et, order, is_b in pt_data:
            pt, _ = PeriodTiming.objects.get_or_create(
                period_order=order,
                defaults={'name': name, 'start_time': st, 'end_time': et, 'is_break': is_b}
            )
            timings_map[order] = pt

        self.stdout.write(self.style.SUCCESS("[OK] Configured 10 Period Timings (including breaks)"))

        # 3. Create Sample Section, Grades, and Divisions
        sec, _ = Section.objects.get_or_create(name="Higher Secondary", defaults={'order': 1})
        g11, _ = Grade.objects.get_or_create(name="Grade 11", defaults={'section': sec, 'order': 11})
        g12, _ = Grade.objects.get_or_create(name="Grade 12", defaults={'section': sec, 'order': 12})

        div_comm, _ = Division.objects.get_or_create(name="Commerce", defaults={'section': sec})
        div_hum, _ = Division.objects.get_or_create(name="Humanities", defaults={'section': sec})
        div_sci, _ = Division.objects.get_or_create(name="Science", defaults={'section': sec})

        self.stdout.write(self.style.SUCCESS("[OK] Configured Grades & Divisions (Commerce, Humanities, Science)"))

        # 4. Create Sample Teachers
        teachers_data = [
            ("teacher_english", "Muhammed", "K (English)", "eng@school.edu"),
            ("teacher_arabic", "Abdul Basith", "Huda (Arabic)", "arabic@school.edu"),
            ("teacher_accounts", "Shafeeque", "Ali (Accounts)", "acc@school.edu"),
            ("teacher_politics", "Fatima", "Zahra (Politics)", "politics@school.edu"),
            ("teacher_econ", "Rahmathullah", "V (Economics)", "econ@school.edu"),
        ]

        teachers_map = {}
        for uname, fname, lname, email in teachers_data:
            u, created = User.objects.get_or_create(username=uname, defaults={'first_name': fname, 'last_name': lname, 'email': email})
            if created:
                u.set_password("Teacher@123")
                u.save()
            
            p, _ = UserProfile.objects.get_or_create(user=u, defaults={'role': 'teacher'})
            if p.role != 'teacher':
                p.role = 'teacher'
                p.save()
            teachers_map[uname] = u

        self.stdout.write(self.style.SUCCESS("[OK] Configured 5 Sample Teachers"))

        # 5. Create Sample Subjects
        sub_english, _ = Subject.objects.get_or_create(
            name="English Literature", grade=g11,
            defaults={'subject_type': 'division', 'is_common_subject': True, 'max_marks': 100}
        )
        sub_arabic, _ = Subject.objects.get_or_create(
            name="Arabic Studies", grade=g11,
            defaults={'subject_type': 'hadiya', 'is_common_subject': True, 'max_marks': 100}
        )
        sub_accounts, _ = Subject.objects.get_or_create(
            name="Accountancy & Finance", grade=g11, division=div_comm,
            defaults={'subject_type': 'division', 'max_marks': 100}
        )
        sub_politics, _ = Subject.objects.get_or_create(
            name="Political Science", grade=g11, division=div_hum,
            defaults={'subject_type': 'division', 'is_common_subject': True, 'max_marks': 100}
        )
        sub_econ, _ = Subject.objects.get_or_create(
            name="Economics", grade=g11,
            defaults={'subject_type': 'division', 'is_common_subject': True, 'max_marks': 100}
        )

        self.stdout.write(self.style.SUCCESS("[OK] Configured Sample Subjects"))

        # 6. Teacher Subject Assignments
        TeacherSubjectAssignment.objects.get_or_create(teacher=teachers_map["teacher_english"], subject=sub_english, grade=g11, division=div_comm, defaults={'periods_per_week': 5})
        TeacherSubjectAssignment.objects.get_or_create(teacher=teachers_map["teacher_english"], subject=sub_english, grade=g11, division=div_hum, defaults={'periods_per_week': 5})
        TeacherSubjectAssignment.objects.get_or_create(teacher=teachers_map["teacher_accounts"], subject=sub_accounts, grade=g11, division=div_comm, defaults={'periods_per_week': 6})
        TeacherSubjectAssignment.objects.get_or_create(teacher=teachers_map["teacher_politics"], subject=sub_politics, grade=g11, division=div_hum, defaults={'periods_per_week': 6})
        TeacherSubjectAssignment.objects.get_or_create(teacher=teachers_map["teacher_arabic"], subject=sub_arabic, grade=g11, defaults={'periods_per_week': 4})

        # 7. Create Dummy Timetable Slots for Grade 11 Commerce & Humanities (Monday - Friday)
        TimetableSlot.objects.filter(grade=g11).delete()

        # Monday Period 1: COMBINED JOINT CLASS (English - Main Hall A for Commerce & Humanities together)
        combined_grp = str(uuid.uuid4())[:8]
        TimetableSlot.objects.create(
            grade=g11, division=div_comm, day_of_week='monday', period_timing=timings_map[1],
            subject=sub_english, teacher=teachers_map["teacher_english"], room_number="Main Hall A",
            is_combined=True, combined_group_id=combined_grp, academic_year=active_year
        )
        TimetableSlot.objects.create(
            grade=g11, division=div_hum, day_of_week='monday', period_timing=timings_map[1],
            subject=sub_english, teacher=teachers_map["teacher_english"], room_number="Main Hall A",
            is_combined=True, combined_group_id=combined_grp, academic_year=active_year
        )

        # Monday Period 2: Regular Classes
        TimetableSlot.objects.create(
            grade=g11, division=div_comm, day_of_week='monday', period_timing=timings_map[2],
            subject=sub_accounts, teacher=teachers_map["teacher_accounts"], room_number="Room 201",
            is_combined=False, academic_year=active_year
        )
        TimetableSlot.objects.create(
            grade=g11, division=div_hum, day_of_week='monday', period_timing=timings_map[2],
            subject=sub_politics, teacher=teachers_map["teacher_politics"], room_number="Room 202",
            is_combined=False, academic_year=active_year
        )

        # Tuesday Period 1: COMBINED JOINT CLASS (Arabic Studies - Auditorium)
        combined_grp2 = str(uuid.uuid4())[:8]
        TimetableSlot.objects.create(
            grade=g11, division=div_comm, day_of_week='tuesday', period_timing=timings_map[1],
            subject=sub_arabic, teacher=teachers_map["teacher_arabic"], room_number="Auditorium",
            is_combined=True, combined_group_id=combined_grp2, academic_year=active_year
        )
        TimetableSlot.objects.create(
            grade=g11, division=div_hum, day_of_week='tuesday', period_timing=timings_map[1],
            subject=sub_arabic, teacher=teachers_map["teacher_arabic"], room_number="Auditorium",
            is_combined=True, combined_group_id=combined_grp2, academic_year=active_year
        )

        # Wednesday Period 4: COMBINED JOINT CLASS (Economics)
        combined_grp3 = str(uuid.uuid4())[:8]
        TimetableSlot.objects.create(
            grade=g11, division=div_comm, day_of_week='wednesday', period_timing=timings_map[5],
            subject=sub_econ, teacher=teachers_map["teacher_econ"], room_number="Main Hall B",
            is_combined=True, combined_group_id=combined_grp3, academic_year=active_year
        )
        TimetableSlot.objects.create(
            grade=g11, division=div_hum, day_of_week='wednesday', period_timing=timings_map[5],
            subject=sub_econ, teacher=teachers_map["teacher_econ"], room_number="Main Hall B",
            is_combined=True, combined_group_id=combined_grp3, academic_year=active_year
        )

        self.stdout.write(self.style.SUCCESS("[OK] Seeded Dummy Timetable Slots (including Combined Joint Classes)"))
        self.stdout.write(self.style.SUCCESS("[SUCCESS] Timetable Dummy Data Seeding Complete!"))
