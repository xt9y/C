CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Wpedantic
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
INCLUDEDIR ?= $(PREFIX)/include
BUILD := build
TARGET := $(BUILD)/c
UNAME_S := $(shell uname -s)
LDLIBS :=
ifeq ($(UNAME_S),Linux)
LDLIBS += -ldl
endif

.PHONY: all clean install uninstall test

all: $(TARGET)

$(TARGET): src/cli.c src/main.c src/cache_io.h src/perf_v2.h include/cbuild.h
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -include src/cache_io.h -Iinclude -DCBUILD_HEADER_PATH='"$(abspath include/cbuild.h)"' src/cli.c $(LDLIBS) -o $(TARGET)

install: $(TARGET)
	install -d $(DESTDIR)$(BINDIR) $(DESTDIR)$(INCLUDEDIR)
	install -m 755 $(TARGET) $(DESTDIR)$(BINDIR)/c
	rm -f $(DESTDIR)$(INCLUDEDIR)/cbuild.h
	install -m 644 include/cbuild.h $(DESTDIR)$(INCLUDEDIR)/cbuild.h

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/c $(DESTDIR)$(INCLUDEDIR)/cbuild.h

clean:
	rm -rf $(BUILD)

test: $(TARGET)
	sh tests/smoke.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/dependency.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/compiler_only.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/source_dependency.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/mixed_language.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/api_baseline.sh $(abspath include)
	sh tests/direct_header.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/test_command.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/profiles.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/performance.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/advanced_performance.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/parallel_deps.sh $(abspath $(TARGET)) $(abspath include)
	sh tests/install_layout.sh $(abspath .)
