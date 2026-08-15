CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Wpedantic
CPPFLAGS ?=
PORTABILITY_CPPFLAGS := -D_XOPEN_SOURCE=700 -D_POSIX_C_SOURCE=200809L
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
	$(CC) $(CPPFLAGS) $(PORTABILITY_CPPFLAGS) $(CFLAGS) -include src/cache_io.h -Iinclude -DCBUILD_HEADER_PATH='"$(abspath include/cbuild.h)"' src/cli.c $(LDLIBS) -o $(TARGET)

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
	sh .github/ci/run-tests.sh $(abspath $(TARGET)) $(abspath include)
