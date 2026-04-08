# Board of Directors

## Project Overview
The Board of Directors project is designed to streamline the management and communication within non-profit organizations. This application allows board members to track meetings, manage agendas, and communicate effectively.

## Architecture
The system utilizes a microservices architecture, enabling scalability and ease of maintenance. Each component is responsible for a specific functionality and communicates via REST APIs.

### Components:
- **User Service**: Handles authentication and user management.
- **Meeting Service**: Manages meeting scheduling, agendas, and minutes.
- **Notification Service**: Sends reminders and updates to board members.

## Agents
- **Admin Agent**: Responsible for overseeing the system and managing user roles.
- **Board Member Agent**: Interfaces with the application to access meeting information and communicate with other members.

## Workflow
1. **User Registration**: New users register through the User Service.
2. **Meeting Creation**: Admin creates and schedules meetings via the Meeting Service.
3. **Notification**: Board members receive notifications about upcoming meetings.
4. **Meeting Participation**: Members can log in and access meeting details, documents, and agendas.
5. **Post-Meeting Actions**: Minutes are captured and distributed to all members post-meeting.

## Features
- User authentication and role management.
- Scheduling and management of board meetings.
- Document sharing and agenda management.
- Automatic notifications and reminders for meetings.
- Reporting features for tracking attendance and meeting outcomes.

## Installation
To install the Board of Directors project, follow these steps:
1. Clone the repository:
   ```bash
   git clone https://github.com/ObedienceAdara/Board-of-Directors.git
   ```
2. Navigate to the project directory:
   ```bash
   cd Board-of-Directors
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Set up environment variables (see `.env.example` for reference).
5. Start the application:
   ```bash
   npm start
   ```

## Usage
After installation, users can access the application via a web browser at `http://localhost:3000`. 
For first-time users, create an account and log in. Admin users can create new meetings and manage users through the admin panel.

## Configuration
Configuration options are available in the `.env` file. Here are some key configurations:
- `DATABASE_URL`: The URL to connect to the database.
- `JWT_SECRET`: The secret key for JSON Web Tokens.
- `EMAIL_SERVICE`: Configuration for sending emails.

## Technical Details
- **Frontend**: React.js - A JavaScript library for building user interfaces.
- **Backend**: Node.js with Express - A server-side framework for building RESTful APIs.
- **Database**: MongoDB - A NoSQL database for storing application data.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
