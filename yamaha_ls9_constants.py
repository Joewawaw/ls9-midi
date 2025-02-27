# yamaha ls9 MIDI NRPN controller + data values. python constants file
from bidict import bidict

#### Constants
ON_OFF_CTLRS = bidict({
    "CH01" : 0x1b0b, "CH02" : 0x1b8b, "CH03" : 0x1c0b, "CH04" : 0x1c8b, "CH05" : 0x1d0b,
    "CH06" : 0x1d8b, "CH07" : 0x1e0b, "CH08" : 0x1e8b, "CH09" : 0x1f0b, "CH10" : 0x1f8b,
    "CH11" : 0x200b, "CH12" : 0x208b, "CH13" : 0x210b, "CH14" : 0x218b, "CH15" : 0x220b,
    "CH16" : 0x228b, "CH17" : 0x230b, "CH18" : 0x238b, "CH19" : 0x240b, "CH20" : 0x248b,
    "CH21" : 0x250b, "CH22" : 0x258b, "CH23" : 0x260b, "CH24" : 0x268b, "CH25" : 0x270b,
    "CH26" : 0x278b, "CH27" : 0x280b, "CH28" : 0x288b, "CH29" : 0x290b, "CH30" : 0x298b,
    "CH31" : 0x2a0b, "CH32" : 0x2a8b, "CH33" : 0x2b0b, "CH34" : 0x2b8b, "CH35" : 0x2c0b,
    "CH36" : 0x2c8b, "CH37" : 0x2d0b, "CH38" : 0x2d8b, "CH39" : 0x2e0b, "CH40" : 0x2e8b,
    "CH41" : 0x2f0b, "CH42" : 0x2f8b, "CH43" : 0x300b, "CH44" : 0x308b, "CH45" : 0x310b,
    "CH46" : 0x318b, "CH47" : 0x320b, "CH48" : 0x328b, "CH49" : 0x370b, "CH50" : 0x378b,
    "CH51" : 0x380b, "CH52" : 0x388b, "CH53" : 0x390b, "CH54" : 0x398b, "CH55" : 0x3a0b,
    "CH56" : 0x3a8b, "CH57" : 0x3b0b, "CH58" : 0x3b8b, "CH59" : 0x3c0b, "CH60" : 0x3c8b,
    "CH61" : 0x3d0b, "CH62" : 0x3d8b, "CH63" : 0x3e0b, "CH64" : 0x3e8b,

    "MIX1" : 0xb0c,  "MIX2" : 0xb8c,  "MIX3" : 0xc0c,  "MIX4" : 0xc8c,
    "MIX5" : 0xd0c,  "MIX6" : 0xd8c,  "MIX7" : 0xe0c,  "MIX8" : 0xe8c,
    "MIX9" : 0xf0c,  "MIX10": 0xf8c,  "MIX11": 0x100c, "MIX12": 0x108c,
    "MIX13": 0x110c, "MIX14": 0x118c, "MIX15": 0x120c, "MIX16": 0x128c,
    "MT1"  : 0x150c, "MT2"  : 0x158c, "MT3"  : 0x160c, "MT4"  : 0x168c,
    "MT5"  : 0x170c, "MT6"  : 0x178c, "MT7"  : 0x180c, "MT8"  : 0x188c,

    "ST-IN1": 0x338b, "ST-IN2": 0x340b, "ST-IN3": 0x350b, "ST-IN4": 0x360b,
    "ST LR":  0x190c, "MONO":   0x1758
})

FADER_CTLRS = bidict({
    "CH01" : 0x0,    "CH02" : 0x80,   "CH03" : 0x100,  "CH04" : 0x180,  "CH05" : 0x200,
    "CH06" : 0x280,  "CH07" : 0x300,  "CH08" : 0x380,  "CH09" : 0x400,  "CH10" : 0x480,
    "CH11" : 0x500,  "CH12" : 0x580,  "CH13" : 0x600,  "CH14" : 0x680,  "CH15" : 0x700,
    "CH16" : 0x780,  "CH17" : 0x800,  "CH18" : 0x880,  "CH19" : 0x900,  "CH20" : 0x980,
    "CH21" : 0xa00,  "CH22" : 0xa80,  "CH23" : 0xb00,  "CH24" : 0xb80,  "CH25" : 0xc00,
    "CH26" : 0xc80,  "CH27" : 0xd00,  "CH28" : 0xd80,  "CH29" : 0xe00,  "CH30" : 0xe80,
    "CH31" : 0xf00,  "CH32" : 0xf80,  "CH33" : 0x1000, "CH34" : 0x1080, "CH35" : 0x1100,
    "CH36" : 0x1180, "CH37" : 0x1200, "CH38" : 0x1280, "CH39" : 0x1300, "CH40" : 0x1380,
    "CH41" : 0x1400, "CH42" : 0x1480, "CH43" : 0x1500, "CH44" : 0x1580, "CH45" : 0x1600,
    "CH46" : 0x1680, "CH47" : 0x1700, "CH48" : 0x1780, "CH49" : 0x1c00, "CH50" : 0x1c80,
    "CH51" : 0x1d00, "CH52" : 0x1d80, "CH53" : 0x1e00, "CH54" : 0x1e80, "CH55" : 0x1f00,
    "CH56" : 0x1f80, "CH57" : 0x2000, "CH58" : 0x2080, "CH59" : 0x2100, "CH60" : 0x2180,
    "CH61" : 0x2200, "CH62" : 0x2280, "CH63" : 0x2300, "CH64" : 0x2380,
    "MIX1" : 0x3000, "MIX2" : 0x3080, "MIX3" : 0x3100, "MIX4" : 0x3180,
    "MIX5" : 0x3200, "MIX6" : 0x3280, "MIX7" : 0x3300, "MIX8" : 0x3380,
    "MIX9" : 0x3400, "MIX10": 0x3480, "MIX11": 0x3500, "MIX12": 0x3580,
    "MIX13": 0x3600, "MIX14": 0x3680, "MIX15": 0x3700, "MIX16": 0x3780,
    "MT1"  : 0x3a00, "MT2"  : 0x3a80, "MT3"  : 0x3b00, "MT4"  : 0x3b80,
    "MT5"  : 0x3c00, "MT6"  : 0x3c80, "MT7"  : 0x3d00, "MT8"  : 0x3d80,

    "ST-IN1": 0x1880, "ST-IN2": 0x1900, "ST-IN3": 0x1a00, "ST-IN4": 0x1b00,
    "ST LR":  0x3e00, "MONO":   0x3451 #, "MON": 0x
})

TABLA1_PEQ1 = 0x829
TABLA2_PEQ1 = 0x8a9

# "SOF" means "Sends on Fader"
MIX1_SOF_CTLRS = bidict({
    "CH01" : 0x3551, "CH02" : 0x35d1, "CH03" : 0x3651, "CH04" : 0x36d1, "CH05" : 0x3751,
    "CH06" : 0x37d1, "CH07" : 0x3851, "CH08" : 0x38d1, "CH09" : 0x3951, "CH10" : 0x39d1,
    "CH11" : 0x3a51, "CH12" : 0x3ad1, "CH13" : 0x3b51, "CH14" : 0x3bd1, "CH15" : 0x3c51,
    "CH16" : 0x3cd1, "CH17" : 0x3d51, "CH18" : 0x3dd1, "CH19" : 0x3e51, "CH20" : 0x3ed1,
    "CH21" : 0x3f51, "CH22" : 0x3fd1, "CH23" : 0x52,   "CH24" : 0xd2,   "CH25" : 0x152,
    "CH26" : 0x1d2,  "CH27" : 0x252,  "CH28" : 0x2d2,  "CH29" : 0x352,  "CH30" : 0x3d2,
    "CH31" : 0x452,  "CH32" : 0x4d2,  "CH33" : 0x552,  "CH34" : 0x5d2,  "CH35" : 0x652,
    "CH36" : 0x6d2,  "CH37" : 0x752,  "CH38" : 0x7d2,  "CH39" : 0x852,  "CH40" : 0x8d2,
    "CH41" : 0x952,  "CH42" : 0x9d2,  "CH43" : 0xa52,  "CH44" : 0xad2,  "CH45" : 0xb52,
    "CH46" : 0xbd2,  "CH47" : 0xc52,  "CH48" : 0xcd2,  "CH49" : 0x1152, "CH50" : 0x11d2,
    "CH51" : 0x1252, "CH52" : 0x12d2, "CH53" : 0x1352, "CH54" : 0x13d2, "CH55" : 0x1452,
    "CH56" : 0x14d2, "CH57" : 0x2521, "CH58" : 0x25a1, "CH59" : 0x2621, "CH60" : 0x26a1,
    "CH61" : 0x2721, "CH62" : 0x27a1, "CH63" : 0x2821, "CH64" : 0x28a1
})



#use this mapping to go from CC number -> Mix number, then use MT5_SOF_CTRLS for the ls9 controller
# 1: main in ear, 2: chorus f, 3: chorus m, 4: lead, 5: harmonium, 6: tabla, 7: crowd, 8: master
USB_MIDI_MT5_SOF_CC_CTLRS = bidict( {
    70 : "MIX3",   71 : "MIX5",   72 : "MIX6",   73 : "MIX8",
    74 : "MIX11",  75 : "MIX10",  76 : "MIX12",  77 : "MT5",
})
USB_MIDI_MT6_SOF_CC_CTLRS = bidict( {
    80 : "MIX4",   81 : "MIX5",   82 : "MIX6",   83 : "MIX8",
    84 : "MIX11",  85 : "MIX10",  86 : "MIX12",  87 : "MT6",
})
#MT5 fader controller is 0x3c00, MT6 is 0x3c80

MT5_SOF_CTRLS = bidict({
    "MIX1" : 0x2b0a,  "MIX2" : 0x2b8a,  "MIX3" : 0xc0c,  "MIX4" : 0xc8c,
    "MIX5" : 0xd0,  "MIX6" : 0xd8c,  "MIX7" : 0xe0c,  "MIX8" : 0xe8c,
    "MIX9" : 0xf0c,  "MIX10": 0xf8c,  "MIX11": 0x100c, "MIX12": 0x108c,
    "MIX13": 0x110c, "MIX14": 0x118c, "MIX15": 0x120c, "MIX16": 0x128c
})

MT6_SOF_CTRLS = bidict({
    "MIX1" : 0xb0c,  "MIX2" : 0xb8c,  "MIX3" : 0xc0c,  "MIX4" : 0xc8c,
    "MIX5" : 0xd0c,  "MIX6" : 0xd8c,  "MIX7" : 0xe0c,  "MIX8" : 0xe8c,
    "MIX9" : 0xf0c,  "MIX10": 0xf8c,  "MIX11": 0x100c, "MIX12": 0x108c,
    "MIX13": 0x110c, "MIX14": 0x118c, "MIX15": 0x120c, "MIX16": 0x128c
})

# values to switch a channel ON/OFF
CH_ON_VALUE  = 0x3FFF
CH_OFF_VALUE = 0x0000

# relevant values for fader controlling
FADE_10DB_VALUE = 0xFFFF ######################
FADE_0DB_VALUE =    0x3370
FADE_50DB_VALUE =   0xad0
FADE_60DB_VALUE =   0x7b0
FADE_NEGINF_VALUE = 0x0

# controller for STLR / MONO send to MT3
ST_LR_SEND_TO_MT3 = 0x1f0a
MONO_SEND_TO_MT3 =  0x3d57

MONO_SEND_TO_MT1  = 0x3757
MIX16_SEND_TO_MT1 = 0x68a
STLR_SEND_TO_MT2  = 0x140a
MIX16_SEND_TO_MT2 = 0x118a

# Mappings for chorus <-> lead automations. WL Mics cycle between 3 states: M.C., chorus & lead
CHORUS_TO_LEAD_MAPPING = bidict({
    "CH01" : "CH33",  "CH02" : "CH34",  "CH03" : "CH35",  "CH04" : "CH36",  "CH05" : "CH37",
    "CH06" : "CH38",  "CH07" : "CH39",  "CH08" : "CH40",  "CH09" : "CH41",  "CH10" : "CH42"
})

WIRELESS_MC_TO_CHR_MAPPING = bidict({
    "CH11" : "CH47",    "CH12" : "CH48",    "CH13" : "CH49",    "CH14" : "CH50"
})

WIRELESS_MC_TO_LEAD_MAPPING = bidict({
    "CH11" : "CH43",    "CH12" : "CH44",    "CH13" : "CH45",    "CH14" : "CH46"
})

WIRELESS_CHR_TO_LEAD_MAPPING = bidict({
    "CH47" : "CH43",    "CH48" : "CH44",    "CH49" : "CH45",    "CH50" : "CH46"
})

#MIDI defined constants for CC commands & NRPN sequence
CC_CMD_BYTE = 0xB0
NRPN_BYTE_1 = 0x62
NRPN_BYTE_2 = 0x63
NRPN_BYTE_3 = 0x06
NRPN_BYTE_4 = 0x26

####################################################################################################
# NPRN message structure for Yamaha LS9 (messages are 7 bits):
# CC cmd #   Byte 1   Byte 2   Byte 3
#        1   0xB0     0x62     <CONTROLLER[0]>
#        2   0xB0     0x63     <CONTROLLER[1]>
#        3   0xB0     0x06     <DATA[0]>
#        4   0xB0     0x26     <DATA[1]>
