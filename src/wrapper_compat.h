#ifndef C_WRAPPER_COMPAT_H
#define C_WRAPPER_COMPAT_H

#ifdef __APPLE__
#include <stddef.h>
#include <sys/sysctl.h>
#include <unistd.h>

static inline long c_wrapper_online_cpus(int name) {
    (void)name;
    int logical_cpus = 1;
    size_t size = sizeof(logical_cpus);
    if (sysctlbyname("hw.logicalcpu", &logical_cpus, &size, NULL, 0) == 0 && logical_cpus > 0)
        return logical_cpus;
    return 1;
}

#ifndef _SC_NPROCESSORS_ONLN
#define _SC_NPROCESSORS_ONLN 0
#endif
#define sysconf(name) c_wrapper_online_cpus(name)
#endif

#endif
