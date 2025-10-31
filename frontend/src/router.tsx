import { createBrowserRouter } from 'react-router-dom';
import Layout from './components/Layout';
import CreateTask from './pages/CreateTask';
import TaskList from './pages/TaskList';
import TaskResults from './pages/TaskResults';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      {
        index: true,
        element: <CreateTask />,
      },
      {
        path: 'tasks',
        element: <TaskList />,
      },
      {
        path: 'tasks/:taskId/results',
        element: <TaskResults />,
      },
    ],
  },
]);
