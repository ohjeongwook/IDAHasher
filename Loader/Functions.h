#pragma once
#pragma warning(disable:4200)
#include <windows.h>
#include <unordered_map>
#include <unordered_set>
#include <list>

#include "Structures.h"
#include "DisassemblyReader.h"
#include "BasicBlocks.h"

using namespace std;
using namespace stdext;

class Functions
{
private:
    int m_fileID;
    DisassemblyReader* m_pdisassemblyReader;
    DisassemblyHashMaps m_disassemblyHashMaps;
    BasicBlocks* m_pbasicBlocks;

    multimap <va_t, va_t> m_blockToFunction;
    multimap <va_t, va_t> m_functionToBlock;
    unordered_set <va_t> m_functionHeads;

public:
    Functions(BasicBlocks *p_basicBlocks = NULL);
    vector <va_t>* GetFunctionAddresses();
    list <AddressRange> GetFunctionBasicBlocks(unsigned long FunctionAddress);
    void LoadBlockFunctionMaps();
    void ClearBlockFunctionMaps();
    BOOL FixFunctionAddresses();
    bool GetFunctionAddress(va_t address, va_t& functionAddress);
    bool IsFunctionBlock(va_t block, va_t function);
    multimap <va_t, va_t>* GetFunctionToBlock();
};