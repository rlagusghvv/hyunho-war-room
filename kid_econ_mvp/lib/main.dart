import 'dart:math';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const KidEconMvpApp());
}

enum DifficultyLevel { easy, normal, hard }

extension DifficultyLabel on DifficultyLevel {
  String get label => switch (this) {
        DifficultyLevel.easy => '쉬움',
        DifficultyLevel.normal => '보통',
        DifficultyLevel.hard => '어려움',
      };

  String get questName => switch (this) {
        DifficultyLevel.easy => '초원 입문 코스',
        DifficultyLevel.normal => '협곡 전략 코스',
        DifficultyLevel.hard => '화산 마스터 코스',
      };

  int get hintPenalty => switch (this) {
        DifficultyLevel.easy => 15,
        DifficultyLevel.normal => 25,
        DifficultyLevel.hard => 35,
      };
}

class KidEconMvpApp extends StatelessWidget {
  const KidEconMvpApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: '뉴스 포트폴리오 탐험대',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6C63FF), brightness: Brightness.light),
        textTheme: const TextTheme(
          titleLarge: TextStyle(fontWeight: FontWeight.w900),
          titleMedium: TextStyle(fontWeight: FontWeight.w800),
          bodyLarge: TextStyle(height: 1.4),
        ),
      ),
      home: const BootstrapPage(),
    );
  }
}

class BootstrapPage extends StatefulWidget {
  const BootstrapPage({super.key});

  @override
  State<BootstrapPage> createState() => _BootstrapPageState();
}

class _BootstrapPageState extends State<BootstrapPage> {
  bool _loading = true;
  late AppState _state;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    _state = await AppStateStore.load();
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return GameHomePage(initialState: _state);
  }
}

class Scenario {
  const Scenario({
    required this.id,
    required this.title,
    required this.news,
    required this.goodIndustries,
    required this.badIndustries,
    required this.options,
    required this.correctOption,
    required this.quizQuestion,
    required this.quizChoices,
    required this.quizAnswer,
  });

  final int id;
  final String title;
  final String news;
  final List<String> goodIndustries;
  final List<String> badIndustries;
  final List<String> options;
  final int correctOption;
  final String quizQuestion;
  final List<String> quizChoices;
  final int quizAnswer;
}

class ScenarioResult {
  const ScenarioResult({
    required this.scenarioId,
    required this.invested,
    required this.profit,
    required this.returnPercent,
    required this.quizCorrect,
    required this.hintUsed,
    required this.difficulty,
    required this.timestamp,
  });

  final int scenarioId;
  final int invested;
  final int profit;
  final int returnPercent;
  final bool quizCorrect;
  final bool hintUsed;
  final DifficultyLevel difficulty;
  final DateTime timestamp;
}

class AppState {
  const AppState({
    required this.playerName,
    required this.cash,
    required this.currentScenario,
    required this.results,
    required this.bestStreak,
    required this.onboarded,
    required this.selectedDifficulty,
  });

  factory AppState.initial() => const AppState(
        playerName: '탐험대원',
        cash: 1000,
        currentScenario: 0,
        results: [],
        bestStreak: 0,
        onboarded: false,
        selectedDifficulty: DifficultyLevel.easy,
      );

  final String playerName;
  final int cash;
  final int currentScenario;
  final List<ScenarioResult> results;
  final int bestStreak;
  final bool onboarded;
  final DifficultyLevel selectedDifficulty;

  int get solvedCount => results.length;
  int get quizCorrectCount => results.where((e) => e.quizCorrect).length;
  int get totalProfit => results.fold(0, (sum, e) => sum + e.profit);
  int get hintUsedCount => results.where((e) => e.hintUsed).length;

  double get avgReturn {
    if (results.isEmpty) return 0;
    final sum = results.fold<int>(0, (acc, e) => acc + e.returnPercent);
    return sum / results.length;
  }

  AppState copyWith({
    String? playerName,
    int? cash,
    int? currentScenario,
    List<ScenarioResult>? results,
    int? bestStreak,
    bool? onboarded,
    DifficultyLevel? selectedDifficulty,
  }) {
    return AppState(
      playerName: playerName ?? this.playerName,
      cash: cash ?? this.cash,
      currentScenario: currentScenario ?? this.currentScenario,
      results: results ?? this.results,
      bestStreak: bestStreak ?? this.bestStreak,
      onboarded: onboarded ?? this.onboarded,
      selectedDifficulty: selectedDifficulty ?? this.selectedDifficulty,
    );
  }
}

class AppStateStore {
  static const _kPlayerName = 'playerName';
  static const _kCash = 'cash';
  static const _kCurrentScenario = 'currentScenario';
  static const _kResults = 'results';
  static const _kBestStreak = 'bestStreak';
  static const _kOnboarded = 'onboarded';
  static const _kDifficulty = 'difficulty';

  static Future<AppState> load() async {
    final prefs = await SharedPreferences.getInstance();
    final initial = AppState.initial();
    final raw = prefs.getStringList(_kResults) ?? [];

    final parsed = raw
        .map((line) {
          final parts = line.split('|');
          if (parts.length < 6) return null;
          final legacy = parts.length == 6;
          return ScenarioResult(
            scenarioId: int.tryParse(parts[0]) ?? 0,
            invested: int.tryParse(parts[1]) ?? 0,
            profit: int.tryParse(parts[2]) ?? 0,
            returnPercent: int.tryParse(parts[3]) ?? 0,
            quizCorrect: parts[4] == '1',
            hintUsed: legacy ? false : parts[5] == '1',
            difficulty: legacy ? DifficultyLevel.easy : _difficultyFrom(parts[6]),
            timestamp: DateTime.fromMillisecondsSinceEpoch(
              int.tryParse(legacy ? parts[5] : parts[7]) ?? DateTime.now().millisecondsSinceEpoch,
            ),
          );
        })
        .whereType<ScenarioResult>()
        .toList();

    return AppState(
      playerName: prefs.getString(_kPlayerName) ?? initial.playerName,
      cash: prefs.getInt(_kCash) ?? initial.cash,
      currentScenario: prefs.getInt(_kCurrentScenario) ?? initial.currentScenario,
      results: parsed,
      bestStreak: prefs.getInt(_kBestStreak) ?? initial.bestStreak,
      onboarded: prefs.getBool(_kOnboarded) ?? initial.onboarded,
      selectedDifficulty: _difficultyFrom(prefs.getString(_kDifficulty) ?? 'easy'),
    );
  }

  static DifficultyLevel _difficultyFrom(String raw) {
    return DifficultyLevel.values.firstWhere(
      (e) => e.name == raw,
      orElse: () => DifficultyLevel.easy,
    );
  }

  static Future<void> save(AppState state) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kPlayerName, state.playerName);
    await prefs.setInt(_kCash, state.cash);
    await prefs.setInt(_kCurrentScenario, state.currentScenario);
    await prefs.setInt(_kBestStreak, state.bestStreak);
    await prefs.setBool(_kOnboarded, state.onboarded);
    await prefs.setString(_kDifficulty, state.selectedDifficulty.name);

    final encoded = state.results
        .map((e) => [
              e.scenarioId,
              e.invested,
              e.profit,
              e.returnPercent,
              e.quizCorrect ? 1 : 0,
              e.hintUsed ? 1 : 0,
              e.difficulty.name,
              e.timestamp.millisecondsSinceEpoch,
            ].join('|'))
        .toList();
    await prefs.setStringList(_kResults, encoded);
  }
}

class GameHomePage extends StatefulWidget {
  const GameHomePage({super.key, required this.initialState});

  final AppState initialState;

  @override
  State<GameHomePage> createState() => _GameHomePageState();
}

class _GameHomePageState extends State<GameHomePage> {
  late AppState _state;
  int _tabIndex = 0;

  @override
  void initState() {
    super.initState();
    _state = widget.initialState;
    if (!_state.onboarded) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _showOnboarding());
    }
  }

  Future<void> _showOnboarding() async {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('🧭 뉴스 포트폴리오 탐험대'),
        content: const Text(
          '탐험 지도를 따라 뉴스를 읽고, 근거를 세워 투자 결정을 내려봐요!\n\n'
          '• 쉬움: 기본 연결 찾기\n'
          '• 보통: 근거 + 기간 판단\n'
          '• 어려움: 연쇄 영향 + 리스크 관리\n\n'
          '힌트는 기본 OFF이며, 오답 뒤에만 1회 열려요. (점수 페널티 있음)',
        ),
        actions: [
          FilledButton(
            onPressed: () {
              setState(() => _state = _state.copyWith(onboarded: true));
              _persist();
              Navigator.pop(context);
            },
            child: const Text('탐험 시작!'),
          )
        ],
      ),
    );
  }

  Future<void> _persist() async => AppStateStore.save(_state);

  void _applyScenarioResult(ScenarioResult result) {
    final nextResults = [..._state.results, result];
    final streak = _calcQuizStreak(nextResults);
    setState(() {
      _state = _state.copyWith(
        cash: max(0, _state.cash + result.profit),
        currentScenario: min(scenarios.length, _state.currentScenario + 1),
        results: nextResults,
        bestStreak: max(_state.bestStreak, streak),
      );
      _tabIndex = 1;
    });
    _persist();
  }

  int _calcQuizStreak(List<ScenarioResult> list) {
    var streak = 0;
    for (final item in list.reversed) {
      if (!item.quizCorrect) break;
      streak++;
    }
    return streak;
  }

  void _resetProgress() {
    setState(() {
      _state = AppState.initial().copyWith(
        playerName: _state.playerName,
        onboarded: true,
        selectedDifficulty: _state.selectedDifficulty,
      );
      _tabIndex = 0;
    });
    _persist();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      _PlayTab(
        state: _state,
        onDifficultyChanged: (d) {
          setState(() => _state = _state.copyWith(selectedDifficulty: d));
          _persist();
        },
        onDone: _applyScenarioResult,
      ),
      _WeeklyReportTab(state: _state),
      _GuideTab(onReset: _resetProgress),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('뉴스 포트폴리오 탐험대')),
      body: SafeArea(child: pages[_tabIndex]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tabIndex,
        onDestinationSelected: (v) => setState(() => _tabIndex = v),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.explore), label: '탐험 맵'),
          NavigationDestination(icon: Icon(Icons.insights), label: '리포트'),
          NavigationDestination(icon: Icon(Icons.menu_book), label: '가이드'),
        ],
      ),
    );
  }
}

class _PlayTab extends StatelessWidget {
  const _PlayTab({
    required this.state,
    required this.onDone,
    required this.onDifficultyChanged,
  });

  final AppState state;
  final ValueChanged<ScenarioResult> onDone;
  final ValueChanged<DifficultyLevel> onDifficultyChanged;

  @override
  Widget build(BuildContext context) {
    final done = state.currentScenario >= scenarios.length;

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _MascotMapHeader(state: state),
          const SizedBox(height: 10),
          _DifficultySelector(current: state.selectedDifficulty, onChanged: onDifficultyChanged),
          const SizedBox(height: 10),
          if (done)
            Card(
              color: Colors.green.shade50,
              child: const Padding(
                padding: EdgeInsets.all(16),
                child: Text('10개 시나리오 완료! 리포트에서 나의 전략 진화를 확인해보자! 🏆'),
              ),
            )
          else
            Expanded(
              child: ScenarioPlayCard(
                scenario: scenarios[state.currentScenario],
                cash: state.cash,
                difficulty: state.selectedDifficulty,
                onDone: onDone,
              ),
            ),
        ],
      ),
    );
  }
}

class _MascotMapHeader extends StatelessWidget {
  const _MascotMapHeader({required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(colors: [Color(0xFFE0F7FA), Color(0xFFE8EAF6)]),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🐻 가이드 곰이와 함께하는 경제 모험 지도', style: TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Chip(label: Text('보유 자산 ${state.cash}코인')),
              Chip(label: Text('진행 ${state.currentScenario}/10')),
              Chip(label: Text('퀴즈 ${state.quizCorrectCount}/${state.solvedCount}')),
              Chip(label: Text('힌트 사용 ${state.hintUsedCount}회')),
            ],
          ),
        ],
      ),
    );
  }
}

class _DifficultySelector extends StatelessWidget {
  const _DifficultySelector({required this.current, required this.onChanged});

  final DifficultyLevel current;
  final ValueChanged<DifficultyLevel> onChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          children: DifficultyLevel.values
              .map(
                (d) => Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: ChoiceChip(
                      label: Text(d.label),
                      selected: current == d,
                      onSelected: (_) => onChanged(d),
                    ),
                  ),
                ),
              )
              .toList(),
        ),
      ),
    );
  }
}

class ScenarioPlayCard extends StatefulWidget {
  const ScenarioPlayCard({
    super.key,
    required this.scenario,
    required this.cash,
    required this.difficulty,
    required this.onDone,
  });

  final Scenario scenario;
  final int cash;
  final DifficultyLevel difficulty;
  final ValueChanged<ScenarioResult> onDone;

  @override
  State<ScenarioPlayCard> createState() => _ScenarioPlayCardState();
}

class _ScenarioPlayCardState extends State<ScenarioPlayCard> {
  late int _selectedIndustry;
  int? _reasoningAnswer;
  int? _quizAnswer;
  double _riskRatio = 55;
  bool _submitted = false;
  bool _hintUnlocked = false;
  bool _hintUsed = false;
  int _wrongAttempts = 0;
  String? _resultText;

  @override
  void initState() {
    super.initState();
    _selectedIndustry = 0;
  }

  int get _expectedReasoning => switch (widget.difficulty) {
        DifficultyLevel.easy => 0,
        DifficultyLevel.normal => 1,
        DifficultyLevel.hard => 2,
      };

  List<String> get _reasoningChoices => const [
        '뉴스와 직접 연결된 산업 먼저 확인',
        '영향이 몇 주/몇 달 갈지 기간 확인',
        '수혜+피해를 함께 보고 분산 전략 세우기',
      ];

  String get _reasoningQuestion => switch (widget.difficulty) {
        DifficultyLevel.easy => '2) 가장 먼저 볼 근거는?',
        DifficultyLevel.normal => '2) 보통 난이도: 한 단계 깊게 볼 근거는?',
        DifficultyLevel.hard => '2) 어려움 난이도: 2차 영향까지 보는 근거는?',
      };

  int _calcReturnPercent(bool coreCorrect) {
    final base = switch (widget.difficulty) {
      DifficultyLevel.easy => coreCorrect ? 10 : -6,
      DifficultyLevel.normal => coreCorrect ? 14 : -10,
      DifficultyLevel.hard => coreCorrect ? 18 : -14,
    };
    final riskBonus = ((_riskRatio - 50) / 10).round();
    final hardRiskPenalty = widget.difficulty == DifficultyLevel.hard && (_riskRatio < 35 || _riskRatio > 75) ? -4 : 0;
    return base + riskBonus + hardRiskPenalty;
  }

  bool _coreReasoningCorrect() {
    final industryOk = _selectedIndustry == widget.scenario.correctOption;
    final quizOk = _quizAnswer == widget.scenario.quizAnswer;
    final reasoningOk = _reasoningAnswer == _expectedReasoning;

    return switch (widget.difficulty) {
      DifficultyLevel.easy => industryOk && quizOk,
      DifficultyLevel.normal => industryOk && quizOk && reasoningOk,
      DifficultyLevel.hard => industryOk && quizOk && reasoningOk && _riskRatio >= 35 && _riskRatio <= 75,
    };
  }

  Widget _choiceTile({
    required String text,
    required bool selected,
    required VoidCallback? onTap,
  }) {
    return Card(
      elevation: 0,
      color: selected ? const Color(0xFFE8F0FE) : Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: selected ? const Color(0xFF6C63FF) : Colors.black12)),
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 10),
        leading: Icon(selected ? Icons.check_circle : Icons.circle_outlined, color: selected ? const Color(0xFF6C63FF) : Colors.grey),
        title: Text(text),
      ),
    );
  }

  void _submit() {
    if (_quizAnswer == null || _reasoningAnswer == null || _submitted) return;

    final coreCorrect = _coreReasoningCorrect();

    if (!coreCorrect && _wrongAttempts == 0) {
      setState(() {
        _wrongAttempts = 1;
        _hintUnlocked = true;
        _resultText = '아쉽게도 근거가 아직 약해요! 힌트가 열렸어요. 다시 도전해볼까요?';
      });
      return;
    }

    final invested = max(100, (widget.cash * (_riskRatio / 100)).round());
    final returnPercent = _calcReturnPercent(coreCorrect);
    final rawProfit = (invested * returnPercent / 100).round();
    final calmBonus = (_riskRatio >= 35 && _riskRatio <= 70) ? 20 : 0;
    final quizCorrect = _quizAnswer == widget.scenario.quizAnswer;
    final quizBonus = quizCorrect
        ? switch (widget.difficulty) {
            DifficultyLevel.easy => 20,
            DifficultyLevel.normal => 30,
            DifficultyLevel.hard => 40,
          }
        : 0;
    final hintPenalty = _hintUsed ? widget.difficulty.hintPenalty : 0;
    final finalProfit = rawProfit + calmBonus + quizBonus - hintPenalty;

    setState(() {
      _submitted = true;
      _resultText =
          '투자금 $invested코인 · 수익률 $returnPercent%\n손익 ${rawProfit >= 0 ? '+' : ''}$rawProfit코인\n'
          '안정 보너스 +$calmBonus · 퀴즈 +$quizBonus · 힌트 페널티 -$hintPenalty\n'
          '최종 변화: ${finalProfit >= 0 ? '+' : ''}$finalProfit코인';
    });

    widget.onDone(
      ScenarioResult(
        scenarioId: widget.scenario.id,
        invested: invested,
        profit: finalProfit,
        returnPercent: returnPercent,
        quizCorrect: quizCorrect,
        hintUsed: _hintUsed,
        difficulty: widget.difficulty,
        timestamp: DateTime.now(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.scenario;

    return ListView(
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('🗺️ ${widget.difficulty.questName} · 시나리오 ${s.id}', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 6),
                Text(s.title, style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                Text(s.news),
                const SizedBox(height: 10),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  Chip(label: Text('수혜 후보 ${s.goodIndustries.join(', ')}')),
                  Chip(label: Text('피해 후보 ${s.badIndustries.join(', ')}')),
                ])
              ],
            ),
          ),
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('1) 어디에 더 비중을 둘까?'),
                ...List.generate(
                  s.options.length,
                  (i) => _choiceTile(
                    text: s.options[i],
                    selected: _selectedIndustry == i,
                    onTap: _submitted ? null : () => setState(() => _selectedIndustry = i),
                  ),
                ),
                const Divider(),
                Text(_reasoningQuestion),
                ...List.generate(
                  _reasoningChoices.length,
                  (i) => _choiceTile(
                    text: _reasoningChoices[i],
                    selected: _reasoningAnswer == i,
                    onTap: _submitted ? null : () => setState(() => _reasoningAnswer = i),
                  ),
                ),
                const Divider(),
                Text('3) 투자 비율(리스크): ${_riskRatio.round()}%'),
                Slider(
                  value: _riskRatio,
                  min: 20,
                  max: 100,
                  divisions: 8,
                  label: '${_riskRatio.round()}%',
                  onChanged: _submitted ? null : (v) => setState(() => _riskRatio = v),
                ),
              ],
            ),
          ),
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('4) 퀴즈: ${s.quizQuestion}'),
                ...List.generate(
                  s.quizChoices.length,
                  (i) => _choiceTile(
                    text: s.quizChoices[i],
                    selected: _quizAnswer == i,
                    onTap: _submitted ? null : () => setState(() => _quizAnswer = i),
                  ),
                ),
                const SizedBox(height: 8),
                if (_hintUnlocked && !_hintUsed)
                  OutlinedButton.icon(
                    onPressed: () => setState(() => _hintUsed = true),
                    icon: const Icon(Icons.lightbulb),
                    label: Text('힌트 보기 (1회, -${widget.difficulty.hintPenalty}코인)'),
                  ),
                if (_hintUsed)
                  Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(color: Colors.amber.shade100, borderRadius: BorderRadius.circular(12)),
                    child: Text('힌트: "${s.goodIndustries.first}" 같은 직접 수혜 산업 + 기간/분산 근거를 함께 생각해보세요!'),
                  ),
                FilledButton.icon(
                  onPressed: _submitted ? null : _submit,
                  icon: const Icon(Icons.check_circle),
                  label: Text(_wrongAttempts == 0 ? '정답 확인' : '재도전 확정'),
                ),
                if (_resultText != null) ...[
                  const SizedBox(height: 10),
                  Text(_resultText!, style: const TextStyle(fontWeight: FontWeight.w700)),
                ]
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _WeeklyReportTab extends StatelessWidget {
  const _WeeklyReportTab({required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    final chunks = <List<ScenarioResult>>[];
    for (var i = 0; i < state.results.length; i += 5) {
      chunks.add(state.results.sublist(i, min(i + 5, state.results.length)));
    }

    return Padding(
      padding: const EdgeInsets.all(16),
      child: ListView(
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('📈 전체 요약', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 6),
                  Text('평균 수익률: ${state.avgReturn.toStringAsFixed(1)}%'),
                  Text('퀴즈 정확도: ${state.solvedCount == 0 ? 0 : (state.quizCorrectCount / state.solvedCount * 100).round()}%'),
                  Text('최고 연속 정답: ${state.bestStreak}회'),
                  Text('힌트 사용: ${state.hintUsedCount}회'),
                  Text('현재 자산: ${state.cash}코인'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          ...chunks.asMap().entries.map((entry) {
            final week = entry.key + 1;
            final list = entry.value;
            final profit = list.fold<int>(0, (sum, e) => sum + e.profit);
            final correct = list.where((e) => e.quizCorrect).length;
            final riskComment = _riskComment(list);

            return Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('주간 리포트 $week (시나리오 ${list.first.scenarioId}~${list.last.scenarioId})',
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 6),
                    Text('주간 손익: ${profit >= 0 ? '+' : ''}$profit코인'),
                    Text('퀴즈 정답: $correct/${list.length}'),
                    Text('코멘트: $riskComment'),
                  ],
                ),
              ),
            );
          }),
          if (state.results.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text('아직 리포트가 없어요. 탐험 맵에서 첫 시나리오를 플레이해보세요!'),
              ),
            )
        ],
      ),
    );
  }

  String _riskComment(List<ScenarioResult> list) {
    final avg = list.fold<int>(0, (acc, e) => acc + e.returnPercent) / list.length;
    if (avg >= 12) return '근거 추론이 안정적이에요! 이제 분산 전략을 더 섬세하게 다듬어봐요.';
    if (avg >= 0) return '괜찮은 흐름! 기간(단기/중기) 판단을 더하면 점프할 수 있어요.';
    return '오답 뒤 재정비가 중요해요. 힌트 없이 근거를 먼저 정리해보자!';
  }
}

class _GuideTab extends StatelessWidget {
  const _GuideTab({required this.onReset});

  final VoidCallback onReset;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: ListView(
        children: [
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text(
                '학습 목표\n'
                '• 쉬움: 뉴스-산업 직접 연결 찾기\n'
                '• 보통: 영향 지속 기간(단기/중기) 판단\n'
                '• 어려움: 2차 파급 + 분산 전략 설계\n'
                '• 힌트 규칙: 기본 OFF, 오답 후 1회만 사용 가능(점수 차감)',
              ),
            ),
          ),
          const SizedBox(height: 8),
          Card(
            color: Colors.red.shade50,
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('진행 초기화', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  FilledButton.tonal(
                    onPressed: onReset,
                    child: const Text('처음부터 다시 탐험하기'),
                  )
                ],
              ),
            ),
          )
        ],
      ),
    );
  }
}

const scenarios = [
  Scenario(
    id: 1,
    title: '폭염 경보 확대',
    news: '한 달째 폭염이 이어지며 전력 사용량이 급증했어요.',
    goodIndustries: ['냉방가전', '전력설비'],
    badIndustries: ['야외레저', '농업'],
    options: ['냉방가전/전력설비', '야외레저/농업', '둘 다 비슷'],
    correctOption: 0,
    quizQuestion: '폭염 때 단기 수요가 늘기 쉬운 산업은?',
    quizChoices: ['냉방가전', '스키장', '우산 제조'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 2,
    title: '온라인 수업 재확대',
    news: '감염병 확산으로 일부 학교가 온라인 수업으로 전환했어요.',
    goodIndustries: ['교육플랫폼', '태블릿'],
    badIndustries: ['학원 오프라인', '통학버스'],
    options: ['교육플랫폼/태블릿', '오프라인 학원/통학버스', '모르겠어요'],
    correctOption: 0,
    quizQuestion: '온라인 수업 확대의 대표 수혜는?',
    quizChoices: ['태블릿', '통학버스', '놀이공원'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 3,
    title: '친환경 포장 의무화',
    news: '정부가 일회용 플라스틱 규제를 강화했어요.',
    goodIndustries: ['친환경소재', '재활용'],
    badIndustries: ['저가 플라스틱', '일회용품'],
    options: ['친환경소재/재활용', '일회용품/플라스틱', '변화 없음'],
    correctOption: 0,
    quizQuestion: '규제 강화 시 먼저 확인할 것은?',
    quizChoices: ['규제로 불리한 산업', '유행 밈', '연예 뉴스'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 4,
    title: '게임 신작 대흥행',
    news: '국내 게임사가 글로벌 신작 흥행에 성공했어요.',
    goodIndustries: ['게임', '결제플랫폼'],
    badIndustries: ['경쟁 게임사', '오프라인 오락시설'],
    options: ['게임/결제플랫폼', '경쟁 게임사/오프라인 오락시설', '둘 다 하락'],
    correctOption: 0,
    quizQuestion: '흥행 뉴스에서 장기적으로 꼭 볼 지표는?',
    quizChoices: ['이용자 유지율', '하루 검색량만', '광고 문구'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 5,
    title: '국제 유가 급등',
    news: '원유 가격이 급등하면서 운송비 부담이 커졌어요.',
    goodIndustries: ['에너지 개발', '정유'],
    badIndustries: ['항공', '물류'],
    options: ['에너지/정유', '항공/물류', '둘 다 수혜'],
    correctOption: 0,
    quizQuestion: '유가 상승이 부담이 되는 산업은?',
    quizChoices: ['항공', '정유', '태양광'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 6,
    title: 'AI 학습도구 보급',
    news: '학교에서 AI 튜터 앱을 정식 도입하기 시작했어요.',
    goodIndustries: ['에듀테크', '클라우드'],
    badIndustries: ['종이교재 중심'],
    options: ['에듀테크/클라우드', '종이교재 중심', '변화 없음'],
    correctOption: 0,
    quizQuestion: '기술 도입 뉴스에서 보는 핵심은?',
    quizChoices: ['실제 사용자 증가', '광고 색감', '유명인 댓글'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 7,
    title: '태풍으로 물류 차질',
    news: '대형 태풍으로 항만 운영이 일시 중단됐어요.',
    goodIndustries: ['재난대응', '대체운송'],
    badIndustries: ['수출물류', '신선식품 유통'],
    options: ['재난대응/대체운송', '수출물류/신선식품', '영향 미미'],
    correctOption: 0,
    quizQuestion: '재난 뉴스에서 투자 판단 전 해야 할 일은?',
    quizChoices: ['영향 기간 확인', '바로 몰빵', '친구 따라하기'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 8,
    title: '금리 인하 발표',
    news: '중앙은행이 기준금리를 인하했어요.',
    goodIndustries: ['성장주', '부동산 관련'],
    badIndustries: ['고금리 수혜 예금형'],
    options: ['성장주/부동산 관련', '예금형', '모두 하락'],
    correctOption: 0,
    quizQuestion: '금리 인하 시 일반적으로 기대되는 것은?',
    quizChoices: ['대출 부담 완화', '현금가치 급등', '모든 소비 중단'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 9,
    title: '식량 가격 불안',
    news: '이상기후로 국제 곡물 가격이 크게 올랐어요.',
    goodIndustries: ['스마트농업', '대체식품'],
    badIndustries: ['원재료 의존 식품'],
    options: ['스마트농업/대체식품', '원재료 의존 식품', '변화 없음'],
    correctOption: 0,
    quizQuestion: '원재료 가격 급등의 위험은?',
    quizChoices: ['마진 축소', '매출 자동 증가', '비용 자동 감소'],
    quizAnswer: 0,
  ),
  Scenario(
    id: 10,
    title: '전기차 충전 인프라 확대',
    news: '도시 전역에 초급속 충전소가 대거 설치되고 있어요.',
    goodIndustries: ['배터리', '충전인프라'],
    badIndustries: ['내연기관 부품'],
    options: ['배터리/충전인프라', '내연기관 부품', '모두 비슷'],
    correctOption: 0,
    quizQuestion: '장기 트렌드를 판단할 때 중요한 것은?',
    quizChoices: ['인프라 확산 속도', '오늘 댓글 수', '짧은 루머'],
    quizAnswer: 0,
  ),
];
