# Employee and Asset Management System

## Overview
A centralized platform for managing:
- Employee information, roles, and departments
- Company assets (equipment, devices, etc.)
- Asset assignments and maintenance records

## Key Features
- **Employee Management**  
  - Onboarding/offboarding workflows  
  - Department hierarchy  
  - Document storage  

- **Asset Tracking**  
  - Barcode/QR code support  
  - Check-in/check-out system  
  - Maintenance scheduling  

- **Reporting**  
  - Asset utilization reports  
  - Employee assignment history  
  - Depreciation calculations  

## Technical Stack
- **Backend**: Python Django
- **Database**: MySQL
- **Frontend**: Django Templates
- **Authentication**: Django Custom and Inbuild Authentication

### CEO Can:

- **Manage Your Team:** CEOs have full control to add, update, and remove Managers and Employees within the organization.

- **Organize Company Structure:** CEOs can create and manage Divisions and Departments to structure the company efficiently.

- **Track Employee Attendance:** Monitor employee attendance to ensure a productive workforce.

- **Manage Leave Requests:** Approve or reject leave requests from Managers and Employees, ensuring operational continuity.

### Manager Can:

- **Maintain Attendance:** Managers can record and update employee attendance, making it easier to track team productivity.

- **Apply for Leave:** Managers can request time off and have it reviewed by the CEO.


### Employee Can:

- **Check Attendance:** Employees can view their attendance records to stay on top of their work hours.

- **Request Leave:** Submit leave requests to the CEO, ensuring seamless time-off management.

## Installation

To set up this project on your local machine, follow these steps:

1. Clone the repository:
```
git clone https://github.com/pankajshinde5057/Koli-cms.git
```
2. Create a virtual environment and activate it:
```
python -m venv venv
venv\Scripts\activate
```
3. Navigate to the project directory and setup environment:

Create .env File: Create a file named .env in the project directory. Add the following content to the .env file:
or just rename .env.example to .env

4. Install dependencies:
```
pip install -r requirements.txt
```
5. Configure the database settings in settings.py and run migrations:
```
python manage.py makemigrations main_app
python manage.py migrate
```
6. Create a superuser account:
```
python manage.py createsuperuser
```
7. Start the development server:
```
python manage.py runserver
```
8. Access the admin panel at http://localhost:8000/ and log in with the superuser credentials.

## Contributing

Contributions are welcome! If you'd like to contribute to OfficeOps-WPS, feel free to open a pull request. We value your input and appreciate your help in making the app even better.

## License

This project is licensed under the [MIT License](LICENSE.txt).
