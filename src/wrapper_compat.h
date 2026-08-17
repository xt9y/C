#ifndef C_WRAPPER_COMPAT_H
#define C_WRAPPER_COMPAT_H

#ifdef __APPLE__
#ifndef _SC_NPROCESSORS_ONLN
#ifdef _SC_NPROCESSORS_CONF
#define _SC_NPROCESSORS_ONLN _SC_NPROCESSORS_CONF
#else
#define _SC_NPROCESSORS_ONLN (-1)
#endif
#endif
#endif

#endif
