/* =========================================================================================

   This is an auto-generated file: Any edits you make may be overwritten!

*/

#pragma once

namespace BinaryData
{
    extern const char*   IBMPlexMonoRegular_ttf;
    const int            IBMPlexMonoRegular_ttfSize = 135580;

    extern const char*   IBMPlexMonoMedium_ttf;
    const int            IBMPlexMonoMedium_ttfSize = 136704;

    extern const char*   IBMPlexMonoSemiBold_ttf;
    const int            IBMPlexMonoSemiBold_ttfSize = 140216;

    extern const char*   IBMPlexMonoBold_ttf;
    const int            IBMPlexMonoBold_ttfSize = 137784;

    // Number of elements in the namedResourceList and originalFileNames arrays.
    const int namedResourceListSize = 4;

    // Points to the start of a list of resource names.
    extern const char* namedResourceList[];

    // Points to the start of a list of resource filenames.
    extern const char* originalFilenames[];

    // If you provide the name of one of the binary resource variables above, this function will
    // return the corresponding data and its size (or a null pointer if the name isn't found).
    const char* getNamedResource (const char* resourceNameUTF8, int& dataSizeInBytes);

    // If you provide the name of one of the binary resource variables above, this function will
    // return the corresponding original, non-mangled filename (or a null pointer if the name isn't found).
    const char* getNamedResourceOriginalFilename (const char* resourceNameUTF8);
}
