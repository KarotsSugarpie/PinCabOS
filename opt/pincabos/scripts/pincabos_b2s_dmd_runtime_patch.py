#!/usr/bin/env python3
# PINCABOS_B2S_DMD_RUNTIME_PATCH_V2
from pathlib import Path
import sys

root = Path(sys.argv[1])
header = root / "plugins/b2slegacy/utils/DMDOverlay.h"
source = root / "plugins/b2slegacy/utils/DMDOverlay.cpp"

h = header.read_text(encoding="utf-8")
cpp = source.read_text(encoding="utf-8")

old_h_include = '#include <future>\n'
new_h_include = '#include <future>\n#include <chrono>\n#include <filesystem>\n'
if old_h_include not in h:
    raise SystemExit("DMDOverlay.h: include attendu absent")
h = h.replace(old_h_include, new_h_include, 1)

old_h_private = '''private:
   ivec4 SearchDmdSubFrame(VPXTexture image, float dmdAspectRatio) const;
'''
new_h_private = '''private:
   ivec4 SearchDmdSubFrame(VPXTexture image, float dmdAspectRatio) const;
   void RefreshRuntimeOverride();
   void RestoreBaseSettings();
   void PublishRuntimeState();
'''
if old_h_private not in h:
    raise SystemExit("DMDOverlay.h: bloc private attendu absent")
h = h.replace(old_h_private, new_h_private, 1)

old_h_tail = '''   bool m_stopSearching = false;
   std::future<ivec4> m_frameSearch;
};
'''
new_h_tail = '''   bool m_stopSearching = false;
   std::future<ivec4> m_frameSearch;

   bool m_isScoreView = false;
   bool m_baseEnable = false;
   bool m_baseDetectDmdFrame = false;
   ivec4 m_baseFrame;
   bool m_runtimeOverride = false;
   std::chrono::steady_clock::time_point m_nextRuntimeCheck {};
   ivec4 m_lastPublishedFrame;
   bool m_lastPublishedAuto = false;
   bool m_lastPublishedEnable = false;
   bool m_hasPublishedState = false;
};
'''
if old_h_tail not in h:
    raise SystemExit("DMDOverlay.h: fin attendue absente")
h = h.replace(old_h_tail, new_h_tail, 1)

old_cpp_includes = '''#include <cmath>
#include <vector>
#include <stack>
#include <algorithm>
'''
new_cpp_includes = '''#include <cmath>
#include <vector>
#include <stack>
#include <algorithm>
#include <fstream>
#include <unordered_map>
#include <system_error>
#include <unistd.h>
'''
if old_cpp_includes not in cpp:
    raise SystemExit("DMDOverlay.cpp: includes attendus absents")
cpp = cpp.replace(old_cpp_includes, new_cpp_includes, 1)

namespace_marker = 'namespace B2SLegacy {\n\n'
runtime_helpers = r'''namespace B2SLegacy {

namespace
{
const std::filesystem::path kPinCabOSRuntimeDir("/run/pincabos-b2s-dmd-tuner");
const std::filesystem::path kPinCabOSCommandFile = kPinCabOSRuntimeDir / "command.env";
const std::filesystem::path kPinCabOSStateFile = kPinCabOSRuntimeDir / "state.env";
const char* kPinCabOSRuntimeEngine = "PINCABOS_B2S_DMD_RUNTIME_V2";

bool ReadEnvFile(const std::filesystem::path& path, std::unordered_map<std::string, std::string>& values)
{
   std::ifstream input(path);
   if (!input.is_open())
      return false;

   std::string line;
   while (std::getline(input, line))
   {
      const size_t sep = line.find('=');
      if (sep == std::string::npos)
         continue;
      values[line.substr(0, sep)] = line.substr(sep + 1);
   }
   return true;
}

int EnvInt(const std::unordered_map<std::string, std::string>& values, const std::string& key, int fallback)
{
   const auto it = values.find(key);
   if (it == values.end())
      return fallback;
   try
   {
      return std::stoi(it->second);
   }
   catch (...)
   {
      return fallback;
   }
}

bool EnvBool(const std::unordered_map<std::string, std::string>& values, const std::string& key, bool fallback)
{
   return EnvInt(values, key, fallback ? 1 : 0) != 0;
}
}

'''
if namespace_marker not in cpp:
    raise SystemExit("DMDOverlay.cpp: namespace attendu absent")
cpp = cpp.replace(namespace_marker, runtime_helpers, 1)

old_load_start = '''void DMDOverlay::LoadSettings(bool isScoreView)
{
   if (isScoreView)
'''
new_load_start = '''void DMDOverlay::LoadSettings(bool isScoreView)
{
   m_isScoreView = isScoreView;

   if (isScoreView)
'''
if old_load_start not in cpp:
    raise SystemExit("DMDOverlay.cpp: LoadSettings attendu absent")
cpp = cpp.replace(old_load_start, new_load_start, 1)

old_load_end = '''      }
   }
}

void DMDOverlay::UpdateBackgroundImage(VPXTexture backImage)
'''
new_load_end = '''      }
   }

   m_baseEnable = m_enable;
   m_baseDetectDmdFrame = m_detectDmdFrame;
   m_baseFrame = m_frame;
}

void DMDOverlay::RestoreBaseSettings()
{
   const bool switchToAuto = !m_detectDmdFrame && m_baseDetectDmdFrame;

   m_enable = m_baseEnable;
   m_detectDmdFrame = m_baseDetectDmdFrame;
   m_frame = m_baseFrame;
   m_runtimeOverride = false;

   if (switchToAuto)
   {
      m_frame = ivec4();
      m_detectSrcId.id = 0;
   }
}

void DMDOverlay::RefreshRuntimeOverride()
{
   if (!m_isScoreView)
      return;

   const auto now = std::chrono::steady_clock::now();
   if (now < m_nextRuntimeCheck)
      return;

   m_nextRuntimeCheck = now + std::chrono::milliseconds(40);

   std::unordered_map<std::string, std::string> values;
   if (!ReadEnvFile(kPinCabOSCommandFile, values))
   {
      if (m_runtimeOverride)
         RestoreBaseSettings();
      return;
   }

   const int targetPid = EnvInt(values, "PID", -1);
   if (targetPid != static_cast<int>(getpid()))
   {
      if (m_runtimeOverride)
         RestoreBaseSettings();
      return;
   }

   const bool enabled = EnvBool(values, "ENABLED", true);
   const bool autoPosition = EnvBool(values, "AUTO", false);
   const bool switchToAuto = !m_detectDmdFrame && autoPosition;

   m_enable = enabled;
   m_runtimeOverride = true;

   if (autoPosition)
   {
      m_detectDmdFrame = true;
      if (switchToAuto)
      {
         m_frame = ivec4();
         m_detectSrcId.id = 0;
      }
   }
   else
   {
      m_detectDmdFrame = false;
      m_frame.x = std::clamp(EnvInt(values, "X", m_frame.x), 0, 65535);
      m_frame.y = std::clamp(EnvInt(values, "Y", m_frame.y), 0, 65535);
      m_frame.z = std::clamp(EnvInt(values, "W", m_frame.z), 1, 65535);
      m_frame.w = std::clamp(EnvInt(values, "H", m_frame.w), 1, 65535);
   }
}

void DMDOverlay::PublishRuntimeState()
{
   if (!m_isScoreView)
      return;

   if (m_hasPublishedState
      && m_lastPublishedFrame.x == m_frame.x
      && m_lastPublishedFrame.y == m_frame.y
      && m_lastPublishedFrame.z == m_frame.z
      && m_lastPublishedFrame.w == m_frame.w
      && m_lastPublishedAuto == m_detectDmdFrame
      && m_lastPublishedEnable == m_enable)
      return;

   std::error_code ec;
   std::filesystem::create_directories(kPinCabOSRuntimeDir, ec);
   if (ec)
      return;

   const auto tempFile = kPinCabOSRuntimeDir / ("state.env.tmp." + std::to_string(getpid()));
   std::ofstream output(tempFile, std::ios::trunc);
   if (!output.is_open())
      return;

   output << "PID=" << getpid() << '\\n';
   output << "ENGINE=" << kPinCabOSRuntimeEngine << '\\n';
   output << "BACKEND=legacy" << '\\n';
   output << "SOURCE=B2SLegacy-runtime" << '\\n';
   output << "ENABLED=" << (m_enable ? 1 : 0) << '\\n';
   output << "AUTO=" << (m_detectDmdFrame ? 1 : 0) << '\\n';
   output << "OVERRIDE=" << (m_runtimeOverride ? 1 : 0) << '\\n';
   output << "X=" << m_frame.x << '\\n';
   output << "Y=" << m_frame.y << '\\n';
   output << "W=" << m_frame.z << '\\n';
   output << "H=" << m_frame.w << '\\n';
   output.close();

   std::filesystem::rename(tempFile, kPinCabOSStateFile, ec);
   if (ec)
   {
      std::filesystem::remove(kPinCabOSStateFile, ec);
      ec.clear();
      std::filesystem::rename(tempFile, kPinCabOSStateFile, ec);
   }

   if (!ec)
   {
      m_lastPublishedFrame = m_frame;
      m_lastPublishedAuto = m_detectDmdFrame;
      m_lastPublishedEnable = m_enable;
      m_hasPublishedState = true;
   }
}

void DMDOverlay::UpdateBackgroundImage(VPXTexture backImage)
'''
if old_load_end not in cpp:
    raise SystemExit("DMDOverlay.cpp: fin LoadSettings attendue absente")
cpp = cpp.replace(old_load_end, new_load_end, 1)

old_render_start = '''void DMDOverlay::Render(VPXRenderContext2D* ctx)
{
   if (!m_enable)
      return;
'''
new_render_start = '''void DMDOverlay::Render(VPXRenderContext2D* ctx)
{
   RefreshRuntimeOverride();
   PublishRuntimeState();

   if (!m_enable)
      return;
'''
if old_render_start not in cpp:
    raise SystemExit("DMDOverlay.cpp: début Render attendu absent")
cpp = cpp.replace(old_render_start, new_render_start, 1)

old_future = '''   if (m_frameSearch.valid() && m_frameSearch.wait_for(std::chrono::seconds(0)) == std::future_status::ready)
      m_frame = m_frameSearch.get();

   if (m_frame.z == 0 || m_frame.w == 0)
'''
new_future = '''   if (m_frameSearch.valid() && m_frameSearch.wait_for(std::chrono::seconds(0)) == std::future_status::ready)
   {
      const ivec4 detectedFrame = m_frameSearch.get();
      if (m_detectDmdFrame)
         m_frame = detectedFrame;
   }

   PublishRuntimeState();

   if (m_frame.z == 0 || m_frame.w == 0)
'''
if old_future not in cpp:
    raise SystemExit("DMDOverlay.cpp: bloc future attendu absent")
cpp = cpp.replace(old_future, new_future, 1)

header.write_text(h, encoding="utf-8")
source.write_text(cpp, encoding="utf-8")
print("GO [√] DMDOverlay patché pour le runtime PinCabOS.")
