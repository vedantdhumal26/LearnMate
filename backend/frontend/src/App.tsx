import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { LandingPage } from '@/pages/LandingPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { CreateCoursePage } from '@/pages/CreateCoursePage';
import { CoursePage } from '@/pages/CoursePage';
import { TutorPage } from '@/pages/TutorPage';
import { AssessmentsPage } from '@/pages/AssessmentsPage';
import { AssessmentTakePage } from '@/pages/AssessmentTakePage';
import { AssessmentResultsPage } from '@/pages/AssessmentResultsPage';
import { LearningDashboardPage } from '@/pages/LearningDashboardPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/courses/new" element={<CreateCoursePage />} />
        <Route path="/courses/:courseId" element={<CoursePage />} />
        <Route path="/courses/:courseId/tutor" element={<TutorPage />} />
        <Route path="/courses/:courseId/assessments" element={<AssessmentsPage />} />
        <Route path="/courses/:courseId/assessments/:assessmentId" element={<AssessmentTakePage />} />
        <Route path="/courses/:courseId/assessments/:assessmentId/results" element={<AssessmentResultsPage />} />
        <Route path="/courses/:courseId/learning" element={<LearningDashboardPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
