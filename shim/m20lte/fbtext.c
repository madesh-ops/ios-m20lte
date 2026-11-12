/* SPDX-License-Identifier: GPL-2.0-only
 * Text on the m20lte firmware framebuffer. Framebuffer and DECON trigger
 * values follow uniLoader board-a30.c (0xec000000, 1080x2340
 * ARGB8888; DECON_F 0x14860000 +0x70). Runs with the MMU off, so every
 * access is aligned and the code is position independent.
 */
#include "fbtext.h"

#define DECON_F 0x14860000UL
#define HW_SW_TRIG_CONTROL 0x70U
#define HW_TRIG_EN 0x1281U  /* uniLoader board-a30.c a30_init */
#define SCALE 5U
#define CELL_W (6U * SCALE)
#define CELL_H (10U * SCALE)
#define LEFT 36U
#define TOP 200U

/* The same compact 5x7 font as the a5xelte display console. */
struct glyph { char ch; uint8_t rows[7]; };
static const struct glyph font[] = {
    {' ',{0,0,0,0,0,0,0}}, {'-',{0,0,0,31,0,0,0}},
    {':',{0,4,4,0,4,4,0}}, {'?',{14,17,1,2,4,0,4}},
    {'.',{0,0,0,0,0,12,12}}, {'=',{0,0,31,0,31,0,0}},
    {'0',{14,17,19,21,25,17,14}}, {'1',{4,12,4,4,4,4,14}},
    {'2',{14,17,1,2,4,8,31}}, {'3',{30,1,1,14,1,1,30}},
    {'4',{2,6,10,18,31,2,2}}, {'5',{31,16,30,1,1,17,14}},
    {'6',{6,8,16,30,17,17,14}}, {'7',{31,1,2,4,8,8,8}},
    {'8',{14,17,17,14,17,17,14}}, {'9',{14,17,17,15,1,2,12}},
    {'A',{14,17,17,31,17,17,17}}, {'B',{30,17,17,30,17,17,30}},
    {'C',{14,17,16,16,16,17,14}}, {'D',{30,17,17,17,17,17,30}},
    {'E',{31,16,16,30,16,16,31}}, {'F',{31,16,16,30,16,16,16}},
    {'G',{14,17,16,23,17,17,14}}, {'H',{17,17,17,31,17,17,17}},
    {'I',{14,4,4,4,4,4,14}}, {'J',{7,2,2,2,18,18,12}},
    {'K',{17,18,20,24,20,18,17}}, {'L',{16,16,16,16,16,16,31}},
    {'M',{17,27,21,21,17,17,17}}, {'N',{17,25,21,19,17,17,17}},
    {'O',{14,17,17,17,17,17,14}}, {'P',{30,17,17,30,16,16,16}},
    {'Q',{14,17,17,17,21,18,13}}, {'R',{30,17,17,30,20,18,17}},
    {'S',{15,16,16,14,1,1,30}}, {'T',{31,4,4,4,4,4,4}},
    {'U',{17,17,17,17,17,17,14}}, {'V',{17,17,17,17,17,10,4}},
    {'W',{17,17,17,21,21,21,10}}, {'X',{17,17,10,4,10,17,17}},
    {'Y',{17,17,10,4,4,4,4}}, {'Z',{31,1,2,4,8,16,31}},
};

uint32_t hero_fb_enable(void)
{
    volatile uint32_t *trig = (volatile uint32_t *)(DECON_F + HW_SW_TRIG_CONTROL);
    uint32_t before = *trig;
    /* uniLoader: without auto/HW trigger, CPU writes never reach the panel. */
    *trig = HW_TRIG_EN;
    __asm__ volatile("dsb sy" : : : "memory");
    return before;
}

static const uint8_t *glyph_for(char ch)
{
    if (ch >= 'a' && ch <= 'z') ch -= 'a' - 'A';
    for (unsigned i = 0; i < sizeof(font) / sizeof(font[0]); ++i)
        if (font[i].ch == ch) return font[i].rows;
    return font[3].rows;
}

static void fill_row(unsigned row, uint32_t pixel)
{
    volatile uint32_t *fb = (volatile uint32_t *)HERO_FB_BASE;
    unsigned top = TOP + row * CELL_H;
    for (unsigned y = top; y < top + CELL_H && y < HERO_FB_HEIGHT; ++y)
        for (unsigned x = 0; x < HERO_FB_WIDTH; ++x)
            fb[y * HERO_FB_WIDTH + x] = pixel;
}

/*
 * Mirror every line into TWRP's pstore pmsg zone so it can be read back with
 * `cat /sys/fs/pstore/pmsg-ramoops-0` after the reset, without a photo.
 * TWRP's ramoops: mem_address 0x92400000, mem_size 0x8000, record_size
 * 0x4000 (dump zone first), pmsg_size 0x4000 -> pmsg zone at 0x92404000.
 * persistent_ram_buffer: sig "DBGC", start, size, then the data.
 */
#define PSTORE_PMSG 0x92404000UL
#define PSTORE_SIG 0x43474244U
#define PSTORE_CAP (0x4000U - 12U)

static void pstore_append(const char *s)
{
    volatile uint32_t *hdr = (volatile uint32_t *)PSTORE_PMSG;
    volatile uint8_t *data = (volatile uint8_t *)(PSTORE_PMSG + 12U);
    static int started;
    if (!started) {
        hdr[0] = PSTORE_SIG;
        hdr[1] = 0;
        hdr[2] = 0;
        started = 1;
    }
    uint32_t n = hdr[2];
    for (unsigned i = 0; s[i] && n < PSTORE_CAP - 1U; ++i)
        data[n++] = (uint8_t)s[i];
    if (n < PSTORE_CAP)
        data[n++] = '\n';
    hdr[2] = n;
    __asm__ volatile("dsb sy" : : : "memory");
}

void hero_fb_text(unsigned row, const char *s)
{
    volatile uint32_t *fb = (volatile uint32_t *)HERO_FB_BASE;
    if (s[0] != 'T' || s[1] != 'W')   /* skip the per-second countdown */
        pstore_append(s);
    unsigned top = TOP + row * CELL_H + 2U * SCALE;
    if (top + 7U * SCALE >= HERO_FB_HEIGHT) return;
    fill_row(row, 0xff000000U);
    for (unsigned col = 0; s[col] && LEFT + (col + 1U) * CELL_W <= HERO_FB_WIDTH; ++col) {
        const uint8_t *g = glyph_for(s[col]);
        for (unsigned y = 0; y < 7; ++y)
            for (unsigned x = 0; x < 5; ++x) {
                if (!(g[y] & (1U << (4 - x)))) continue;
                for (unsigned sy = 0; sy < SCALE; ++sy)
                    for (unsigned sx = 0; sx < SCALE; ++sx)
                        fb[(top + y * SCALE + sy) * HERO_FB_WIDTH +
                           LEFT + col * CELL_W + x * SCALE + sx] = 0xffffffffU;
            }
    }
}

/* "LABEL 0123456789ABCDEF" without library helpers. */
void hero_fb_hex(unsigned row, const char *label, uint64_t value)
{
    char line[40];
    unsigned n = 0;
    while (label[n] && n < 20) {
        line[n] = label[n];
        ++n;
    }
    line[n++] = ' ';
    for (int shift = 60; shift >= 0; shift -= 4) {
        unsigned digit = (unsigned)(value >> shift) & 15U;
        line[n++] = (char)(digit < 10 ? '0' + digit : 'A' + digit - 10);
    }
    line[n] = 0;
    hero_fb_text(row, line);
}
