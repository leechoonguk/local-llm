/**
 * The top of every page, ported from the reference application's
 * `CustomBreadcrumbs`.
 *
 * The order is the design: heading, then a one-line description of what the
 * screen is for, then the trail — and the trail's separator is a 4px dot, not a
 * slash. The action sits on the right of the heading row, so "what this screen
 * is" and "what I can do here" are read in one pass.
 */

import { Box, Breadcrumbs, Link, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import type { ReactNode } from 'react'

const SEPARATOR_SIZE = 4

export interface BreadcrumbLink {
  label: string
  href?: string
}

interface PageHeaderProps {
  heading: string
  description?: string
  links: BreadcrumbLink[]
  action?: ReactNode
}

export default function PageHeader({ heading, description, links, action }: PageHeaderProps) {
  return (
    <Box sx={{ mb: 3 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        spacing={{ xs: 1.5, sm: 0 }}
      >
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h4" gutterBottom>
            {heading}
          </Typography>

          {description !== undefined && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {description}
            </Typography>
          )}

          <Breadcrumbs separator={<Separator />}>
            {links.map((link) =>
              link.href === undefined ? (
                <Typography key={link.label} variant="body2" color="text.disabled">
                  {link.label}
                </Typography>
              ) : (
                <Link
                  key={link.label}
                  component={RouterLink}
                  to={link.href}
                  variant="body2"
                  color="inherit"
                >
                  {link.label}
                </Link>
              ),
            )}
          </Breadcrumbs>
        </Box>

        {action !== undefined && <Box sx={{ flexShrink: 0 }}>{action}</Box>}
      </Stack>
    </Box>
  )
}

function Separator() {
  return (
    <Box
      component="span"
      sx={{
        width: SEPARATOR_SIZE,
        height: SEPARATOR_SIZE,
        borderRadius: '50%',
        bgcolor: 'text.disabled',
      }}
    />
  )
}
