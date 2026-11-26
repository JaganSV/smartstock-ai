import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { Link } from 'react-router';

export default function Forbidden() {
  return (
    <Box sx={{ py: 6, textAlign: 'center' }}>
      <Typography variant="h1" gutterBottom>
        403 – Access denied
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        You don&apos;t have permission to view this page.
      </Typography>
      <Button component={Link} to="/dashboard" variant="outlined">
        Go to the dashboard
      </Button>
    </Box>
  );
}
