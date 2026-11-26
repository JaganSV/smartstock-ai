import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { Link } from 'react-router';

export default function NotFound() {
  return (
    <Box sx={{ py: 6, textAlign: 'center' }}>
      <Typography variant="h1" gutterBottom>
        404 – Page not found
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        There is no page at this address.
      </Typography>
      <Button component={Link} to="/dashboard" variant="outlined">
        Go to the dashboard
      </Button>
    </Box>
  );
}
