# Smart Group Expenses - Backend

This is the backend server for the **Smart Group Expenses** project, built with Python, Django, and PostgreSQL. It provides a RESTful API for all frontend functionalities, including user authentication, group and expense management, and a smart debt settlement algorithm.

---

## Table of Contents
- [Features](#features)
- [API Endpoints](#api-endpoints)
- [Built With](#built-with)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Running the Tests](#running-the-tests)
- [Frontend Repository](#frontend-repository)

---

## Features

- **Authentication:** JWT-based authentication (Login, Register, Refresh).
- **CRUD Operations:** Full Create, Read, Update, Delete functionality for Groups and Expenses.
- **Group Management:** Endpoints for adding and removing group members.
- **Optimized Settlement Algorithm:** A dedicated endpoint (`/settle/`) calculates the minimum number of transactions to clear group debts.
- **Permissions:** Granular permissions ensuring users can only access or modify their own data (e.g., only group owners can manage members or delete groups).

---

## API Endpoints

A brief overview of the main API endpoints. All endpoints are prefixed with `/api`.

- `POST /auth/register/` - Register a new user.
- `POST /auth/login/` - Obtain JWT access and refresh tokens.
- `GET, PATCH /auth/user/` - Retrieve or update the authenticated user's profile.
- `GET, POST /groups/` - List user's groups or create a new one.
- `GET, PATCH, DELETE /groups/<id>/` - Retrieve, update, or delete a specific group.
- `POST, DELETE /groups/<id>/members/` - Add or remove a member from a group.
- `GET, POST /groups/<id>/expenses/` - List expenses for a group or add a new one.
- `PATCH, DELETE /groups/<group_id>/expenses/<expense_id>/` - Update or delete a specific expense.
- `GET /groups/<id>/settle/` - Get the optimized settlement plan for a group.

---

## Built With

- **Framework:** [Django](https://www.djangoproject.com/) & [Django REST Framework](https://www.django-rest-framework.org/)
- **Database:** [PostgreSQL](https://www.postgresql.org/)
- **Authentication:** [Simple JWT for Django REST Framework](https://django-rest-framework-simplejwt.readthedocs.io/)
- **Environment:** [Docker](https://www.docker.com/) for PostgreSQL database.
- **Testing:** Django's built-in `TestCase`.

---

## Getting Started

To get the backend server running locally, follow these steps.

### Prerequisites

- [Python](https://www.python.org/) (v3.9 or later)
- [pip](https://pip.pypa.io/en/stable/) & [venv](https://docs.python.org/3/library/venv.html)
- [Docker](https://www.docker.com/) (for running the PostgreSQL database)

### Installation

1.  **Clone the repo:**
    ```sh
    git clone https://github.com/RoRoberto94/smart-group-expenses-backend
    cd smart-group-expenses-backend
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    # On macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # On Windows
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install Python packages:**
    ```sh
    pip install -r requirements.txt
    ```

4.  **Set up the database with Docker:**
    - Make sure Docker Desktop is running.
    - Start the PostgreSQL container:
      ```sh
      docker run --name group-expenses-db -e POSTGRES_USER=devuser -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=group_expenses_db -p 5432:5432 -d postgres
      ```
      (If the container already exists, start it with `docker start group-expenses-db`)

5.  **Set up environment variables:**
    - Create a `.env` file in the root of the project.
    - Add the following variables:
      ```env
      SECRET_KEY='your-strong-random-secret-key-here'
      DATABASE_URL=postgres://devuser:devpass@localhost:5432/group_expenses_db
      ```

6.  **Run database migrations:**
    ```sh
    python manage.py migrate
    ```

7.  **Create a superuser (optional, for admin access):**
    ```sh
    python manage.py createsuperuser
    ```

8.  **Run the development server:**
    ```sh
    python manage.py runserver
    ```
    The API will be available at `http://127.0.0.1:8000/`.

---

## Running the Tests

- **To run the entire test suite:**
  ```sh
  python manage.py test
  ```
- **To run tests for a specific app:**
  ```sh
  python manage.py test expenses
  ```
---

## Frontend Repository
The frontend for this project is a separate React application. You can find its repository here:

[Smart Group Expenses - Frontend](https://github.com/RoRoberto94/smart-group-expenses-frontend)