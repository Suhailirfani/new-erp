# Student Attendance System

A comprehensive Django-based attendance management system for students with support for multiple attendance types and hostel movement tracking.

## Features

### Student Management
- Categorize students by:
  - **Grade** (11, 12, etc.)
  - **Room/Classroom**
  - **Division** (Commerce, Science, Arts, etc.)
  - **Student Type** (Hostel/Day Scholar)

### Attendance Management
- **Multiple Attendance Types per Day:**
  - **Daily Attendance**: Overall daily presence
  - **Period Attendance**: Attendance for each period/subject
  - **Activity Attendance**: Attendance for special activities
  
- **Attendance Status:**
  - Present
  - Absent
  - Late
  - Excused

### Hostel Movement Tracking
- **Departure Information:**
  - Date and Time
  - Escorting Person
  - Reason for departure
  - Expected return date

- **Arrival Information:**
  - Return date
  - Arrival date and time
  - Student signature/name
  - Return status tracking

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd ATTENDANCE
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create a superuser (for admin access):**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

8. **Access the application:**
   - Web Interface: http://127.0.0.1:8000/
   - Admin Panel: http://127.0.0.1:8000/admin/

## Usage

### Setting Up Data

1. **Create Divisions:**
   - Go to Admin Panel → Divisions
   - Add divisions like "Commerce", "Science", "Arts", etc.

2. **Create Rooms:**
   - Go to Admin Panel → Rooms
   - Add classroom/room numbers

3. **Create Periods (for period attendance):**
   - Go to Admin Panel → Periods
   - Add periods with start and end times

4. **Create Activities (for activity attendance):**
   - Go to Admin Panel → Activities
   - Add activities with dates and times

5. **Add Students:**
   - Go to Admin Panel → Students or use the web interface
   - Fill in student details including grade, division, room, and student type

### Marking Attendance

1. **Daily Attendance:**
   - Navigate to "Mark Attendance"
   - Select "Daily" as attendance type
   - Choose date and filter students (optional)
   - Mark attendance for each student
   - Click "Save Attendance"

2. **Period Attendance:**
   - Navigate to "Mark Attendance"
   - Select "Period" as attendance type
   - Choose date, period, and filter students (optional)
   - Mark attendance for each student
   - Click "Save Attendance"

3. **Activity Attendance:**
   - Navigate to "Mark Attendance"
   - Select "Activity" as attendance type
   - Choose date, activity, and filter students (optional)
   - Mark attendance for each student
   - Click "Save Attendance"

### Hostel Movement Tracking

1. **Record Departure:**
   - Go to "Hostel Movements" → "Record New Movement"
   - Select student (only hostel students are shown)
   - Fill in departure details
   - Click "Record Movement"

2. **Update Return:**
   - Go to "Hostel Movements"
   - Click "Update" on a movement record
   - Fill in arrival details
   - Check "Mark as Returned" if student has returned
   - Click "Update Movement"

### Viewing Records

- **Students:** View all students with filtering options
- **Attendance Records:** View all attendance with date range and type filters
- **Hostel Movements:** View all movement records with status filters

## Project Structure

```
ATTENDANCE/
├── attendance_system/      # Main project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── students/               # Main application
│   ├── models.py          # Database models
│   ├── views.py           # View functions
│   ├── admin.py           # Admin configuration
│   ├── urls.py            # URL routing
│   ├── templates/         # HTML templates
│   └── templatetags/      # Custom template filters
├── manage.py
├── requirements.txt
└── README.md
```

## Models

- **Student**: Student information with categorization
- **Division**: Academic divisions (Commerce, Science, etc.)
- **Room**: Classrooms/rooms
- **Period**: Time periods for period-wise attendance
- **Activity**: Special activities
- **Attendance**: Attendance records (daily, period, activity)
- **HostelMovement**: Hostel student movement tracking

## Admin Panel

The Django admin panel provides full CRUD operations for all models. Access it at `/admin/` after creating a superuser.

## Notes

- Multiple attendance records can be created for the same student on the same day (one for daily, multiple for periods, multiple for activities)
- Only hostel students can have movement records
- The system prevents duplicate attendance entries based on type, date, and period/activity

## License

This project is for educational purposes.

