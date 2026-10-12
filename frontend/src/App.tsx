import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { AuthProvider } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { PublicOnlyRoute } from '@/components/PublicOnlyRoute';
import { LandingPage } from '@/pages/LandingPage';
import { LoginPage } from '@/pages/LoginPage';
import { SignupPage } from '@/pages/SignupPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { CreateCoursePage } from '@/pages/CreateCoursePage';
import { CoursePage } from '@/pages/CoursePage';
import { TutorPage } from '@/pages/TutorPage';
import { AssessmentsPage } from '@/pages/AssessmentsPage';
import { AssessmentTakePage } from '@/pages/AssessmentTakePage';
import { AssessmentResultsPage } from '@/pages/AssessmentResultsPage';
import { LearningDashboardPage } from '@/pages/LearningDashboardPage';
import { EvaluationPage } from '@/pages/EvaluationPage';

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            {/* Public landing page */}
            <Route path="/" element={<LandingPage />} />

            {/* Public-only authentication routes */}
            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
            </Route>

            {/* Protected application routes */}
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/courses" element={<DashboardPage />} />
              <Route path="/courses/new" element={<CreateCoursePage />} />
              <Route path="/courses/:courseId" element={<CoursePage />} />
              <Route path="/courses/:courseId/tutor" element={<TutorPage />} />
              <Route path="/courses/:courseId/assessments" element={<AssessmentsPage />} />
              <Route path="/courses/:courseId/assessments/:assessmentId" element={<AssessmentTakePage />} />
              <Route path="/courses/:courseId/assessments/:assessmentId/results" element={<AssessmentResultsPage />} />
              <Route path="/courses/:courseId/learning" element={<LearningDashboardPage />} />
              <Route path="/evaluation" element={<EvaluationPage />} />
            </Route>

            {/* Catch-all fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
