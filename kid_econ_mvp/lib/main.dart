import 'dart:math';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const MoneyExplorerApp());
}

class MoneyExplorerApp extends StatelessWidget {
  const MoneyExplorerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '머니탐험대',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: Colors.teal,
        useMaterial3: true,
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
  late GameState _state;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    _state = await GameStateStore.load();
    if (mounted) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    return HomePage(initialState: _state);
  }
}

enum Difficulty { easy, normal, hard }

class GameState {
  GameState({
    required this.playerName,
    required this.coins,
    required this.day,
    required this.level,
    required this.savedCoins,
    required this.timeLimitMinutes,
    required this.difficulty,
    required this.todayPlayedMinutes,
    required this.lastPlayDate,
    required this.onboarded,
    required this.soundOn,
  });

  factory GameState.initial() => GameState(
        playerName: '탐험대원',
        coins: 30,
        day: 1,
        level: 1,
        savedCoins: 0,
        timeLimitMinutes: 15,
        difficulty: Difficulty.normal,
        todayPlayedMinutes: 0,
        lastPlayDate: DateTime.now(),
        onboarded: false,
        soundOn: true,
      );

  final String playerName;
  final int coins;
  final int day;
  final int level;
  final int savedCoins;
  final int timeLimitMinutes;
  final Difficulty difficulty;
  final int todayPlayedMinutes;
  final DateTime lastPlayDate;
  final bool onboarded;
  final bool soundOn;

  int get netWorth => coins + savedCoins;

  bool get reachedDailyLimit {
    final now = DateTime.now();
    final isSameDay =
        now.year == lastPlayDate.year && now.month == lastPlayDate.month && now.day == lastPlayDate.day;
    if (!isSameDay) return false;
    return todayPlayedMinutes >= timeLimitMinutes;
  }

  GameState copyWith({
    String? playerName,
    int? coins,
    int? day,
    int? level,
    int? savedCoins,
    int? timeLimitMinutes,
    Difficulty? difficulty,
    int? todayPlayedMinutes,
    DateTime? lastPlayDate,
    bool? onboarded,
    bool? soundOn,
  }) {
    return GameState(
      playerName: playerName ?? this.playerName,
      coins: coins ?? this.coins,
      day: day ?? this.day,
      level: level ?? this.level,
      savedCoins: savedCoins ?? this.savedCoins,
      timeLimitMinutes: timeLimitMinutes ?? this.timeLimitMinutes,
      difficulty: difficulty ?? this.difficulty,
      todayPlayedMinutes: todayPlayedMinutes ?? this.todayPlayedMinutes,
      lastPlayDate: lastPlayDate ?? this.lastPlayDate,
      onboarded: onboarded ?? this.onboarded,
      soundOn: soundOn ?? this.soundOn,
    );
  }
}

class GameStateStore {
  static const _kPlayerName = 'playerName';
  static const _kCoins = 'coins';
  static const _kDay = 'day';
  static const _kLevel = 'level';
  static const _kSavedCoins = 'savedCoins';
  static const _kTimeLimit = 'timeLimit';
  static const _kDifficulty = 'difficulty';
  static const _kPlayedMinutes = 'playedMinutes';
  static const _kLastPlayDate = 'lastPlayDate';
  static const _kOnboarded = 'onboarded';
  static const _kSoundOn = 'soundOn';

  static Future<GameState> load() async {
    final prefs = await SharedPreferences.getInstance();
    final fallback = GameState.initial();
    final lastPlayMillis = prefs.getInt(_kLastPlayDate);

    return GameState(
      playerName: prefs.getString(_kPlayerName) ?? fallback.playerName,
      coins: prefs.getInt(_kCoins) ?? fallback.coins,
      day: prefs.getInt(_kDay) ?? fallback.day,
      level: prefs.getInt(_kLevel) ?? fallback.level,
      savedCoins: prefs.getInt(_kSavedCoins) ?? fallback.savedCoins,
      timeLimitMinutes: prefs.getInt(_kTimeLimit) ?? fallback.timeLimitMinutes,
      difficulty: Difficulty.values[(prefs.getInt(_kDifficulty) ?? fallback.difficulty.index)
          .clamp(0, Difficulty.values.length - 1)],
      todayPlayedMinutes: prefs.getInt(_kPlayedMinutes) ?? fallback.todayPlayedMinutes,
      lastPlayDate: lastPlayMillis != null
          ? DateTime.fromMillisecondsSinceEpoch(lastPlayMillis)
          : fallback.lastPlayDate,
      onboarded: prefs.getBool(_kOnboarded) ?? fallback.onboarded,
      soundOn: prefs.getBool(_kSoundOn) ?? fallback.soundOn,
    );
  }

  static Future<void> save(GameState state) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kPlayerName, state.playerName);
    await prefs.setInt(_kCoins, state.coins);
    await prefs.setInt(_kDay, state.day);
    await prefs.setInt(_kLevel, state.level);
    await prefs.setInt(_kSavedCoins, state.savedCoins);
    await prefs.setInt(_kTimeLimit, state.timeLimitMinutes);
    await prefs.setInt(_kDifficulty, state.difficulty.index);
    await prefs.setInt(_kPlayedMinutes, state.todayPlayedMinutes);
    await prefs.setInt(_kLastPlayDate, state.lastPlayDate.millisecondsSinceEpoch);
    await prefs.setBool(_kOnboarded, state.onboarded);
    await prefs.setBool(_kSoundOn, state.soundOn);
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.initialState});

  final GameState initialState;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late GameState _state;
  String? _lastEventMessage;

  @override
  void initState() {
    super.initState();
    _state = _resetDailyIfNeeded(widget.initialState);
    if (!_state.onboarded) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _showOnboarding());
    }
  }

  GameState _resetDailyIfNeeded(GameState state) {
    final now = DateTime.now();
    final sameDay = now.year == state.lastPlayDate.year && now.month == state.lastPlayDate.month && now.day == state.lastPlayDate.day;
    if (sameDay) return state;
    return state.copyWith(todayPlayedMinutes: 0, lastPlayDate: now);
  }

  Future<void> _persist() async {
    await GameStateStore.save(_state);
  }

  Future<void> _showOnboarding() async {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('머니탐험대에 오신 걸 환영해요!'),
        content: const Text(
          '오늘의 목표는 돈을 건강하게 쓰고, 저축 습관을 만드는 거예요.\n\n'
          '1) 미션 카드에서 선택\n'
          '2) 결과를 보고 코인 변화 확인\n'
          '3) 저금통에 코인을 모아 레벨업!',
        ),
        actions: [
          FilledButton(
            onPressed: () {
              setState(() {
                _state = _state.copyWith(onboarded: true);
              });
              _persist();
              Navigator.pop(context);
            },
            child: const Text('시작하기'),
          ),
        ],
      ),
    );
  }

  void _applyResult(EventResult result) {
    final nextCoins = max(0, _state.coins + result.coinDelta - result.spendDelta);
    final nextSaved = max(0, _state.savedCoins + result.saveDelta);

    var nextLevel = _state.level;
    if ((nextSaved ~/ 50) + 1 > nextLevel) {
      nextLevel = (nextSaved ~/ 50) + 1;
    }

    setState(() {
      _state = _state.copyWith(
        coins: nextCoins,
        savedCoins: nextSaved,
        level: nextLevel,
        day: _state.day + 1,
        todayPlayedMinutes: _state.todayPlayedMinutes + 3,
        lastPlayDate: DateTime.now(),
      );
      _lastEventMessage = result.message;
    });
    _persist();
  }

  Future<void> _openParentSettings() async {
    final pinController = TextEditingController();
    final unlocked = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('부모 설정 잠금'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('PIN 1234를 입력하세요 (MVP 고정값)'),
            const SizedBox(height: 8),
            TextField(
              controller: pinController,
              keyboardType: TextInputType.number,
              obscureText: true,
              decoration: const InputDecoration(hintText: 'PIN'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('취소')),
          FilledButton(
            onPressed: () => Navigator.pop(context, pinController.text.trim() == '1234'),
            child: const Text('확인'),
          )
        ],
      ),
    );

    if (unlocked != true || !mounted) return;

    var tempLimit = _state.timeLimitMinutes.toDouble();
    var tempDiff = _state.difficulty;
    var tempSound = _state.soundOn;

    final saved = await showModalBottomSheet<bool>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setInner) => Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('부모 설정', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                Text('일일 플레이 제한: ${tempLimit.toInt()}분'),
                Slider(
                  min: 5,
                  max: 40,
                  divisions: 7,
                  value: tempLimit,
                  onChanged: (v) => setInner(() => tempLimit = v),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<Difficulty>(
                  initialValue: tempDiff,
                  items: const [
                    DropdownMenuItem(value: Difficulty.easy, child: Text('쉬움')),
                    DropdownMenuItem(value: Difficulty.normal, child: Text('보통')),
                    DropdownMenuItem(value: Difficulty.hard, child: Text('어려움')),
                  ],
                  onChanged: (v) {
                    if (v != null) setInner(() => tempDiff = v);
                  },
                  decoration: const InputDecoration(labelText: '난이도'),
                ),
                SwitchListTile(
                  value: tempSound,
                  onChanged: (v) => setInner(() => tempSound = v),
                  title: const Text('효과음(플레이스홀더) 활성화'),
                  contentPadding: EdgeInsets.zero,
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('취소'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('저장'),
                      ),
                    ),
                  ],
                )
              ],
            ),
          ),
        );
      },
    );

    if (saved == true) {
      setState(() {
        _state = _state.copyWith(
          timeLimitMinutes: tempLimit.toInt(),
          difficulty: tempDiff,
          soundOn: tempSound,
        );
      });
      _persist();
    }
  }

  @override
  Widget build(BuildContext context) {
    final cards = buildEventCards(_state.difficulty);

    return Scaffold(
      appBar: AppBar(
        title: const Text('머니탐험대'),
        actions: [
          IconButton(
            tooltip: '부모 설정',
            onPressed: _openParentSettings,
            icon: const Icon(Icons.lock_outline),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              _StatusPanel(state: _state),
              const SizedBox(height: 12),
              if (_state.reachedDailyLimit)
                Card(
                  color: Colors.amber.shade100,
                  child: const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('오늘 플레이 제한 시간에 도달했어요. 내일 다시 탐험해요!'),
                  ),
                )
              else
                Expanded(
                  child: ListView.separated(
                    itemCount: cards.length,
                    separatorBuilder: (context, index) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final card = cards[index];
                      return Card(
                        child: ListTile(
                          leading: CircleAvatar(child: Text(card.emoji)),
                          title: Text(card.title),
                          subtitle: Text(card.description),
                          trailing: const Icon(Icons.play_arrow),
                          onTap: () {
                            final result = card.resolve();
                            _applyResult(result);
                          },
                        ),
                      );
                    },
                  ),
                ),
              if (_lastEventMessage != null) ...[
                const SizedBox(height: 8),
                Text(
                  _lastEventMessage!,
                  style: Theme.of(context).textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
              ]
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusPanel extends StatelessWidget {
  const _StatusPanel({required this.state});

  final GameState state;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${state.playerName} · Lv.${state.level}',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _chip('보유 코인', '${state.coins}'),
                _chip('저축 코인', '${state.savedCoins}'),
                _chip('순자산', '${state.netWorth}'),
                _chip('탐험 Day', '${state.day}'),
                _chip('오늘 플레이', '${state.todayPlayedMinutes}/${state.timeLimitMinutes}분'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, String value) {
    return Chip(label: Text('$label: $value'));
  }
}

class EventCard {
  const EventCard({
    required this.emoji,
    required this.title,
    required this.description,
    required this.resolve,
  });

  final String emoji;
  final String title;
  final String description;
  final EventResult Function() resolve;
}

class EventResult {
  const EventResult({
    required this.coinDelta,
    required this.saveDelta,
    required this.spendDelta,
    required this.message,
  });

  final int coinDelta;
  final int saveDelta;
  final int spendDelta;
  final String message;
}

List<EventCard> buildEventCards(Difficulty difficulty) {
  final rng = Random();
  final multiplier = switch (difficulty) {
    Difficulty.easy => 1,
    Difficulty.normal => 2,
    Difficulty.hard => 3,
  };

  return [
    EventCard(
      emoji: '📚',
      title: '경제 퀴즈 맞히기',
      description: '정답을 맞히면 코인을 얻어요.',
      resolve: () {
        final gain = 5 + rng.nextInt(3) * multiplier;
        return EventResult(
          coinDelta: gain,
          saveDelta: 0,
          spendDelta: 0,
          message: '퀴즈 성공! +$gain 코인을 얻었어요.',
        );
      },
    ),
    EventCard(
      emoji: '💰',
      title: '저금통에 넣기',
      description: '지금 가진 코인 일부를 저축해요.',
      resolve: () {
        final save = 4 + rng.nextInt(3) * multiplier;
        return EventResult(
          coinDelta: 0,
          saveDelta: save,
          spendDelta: 0,
          message: '좋은 습관! 저축 코인 +$save',
        );
      },
    ),
    EventCard(
      emoji: '🛍️',
      title: '사고 싶은 장난감',
      description: '정말 필요한지 생각하고 지출해요.',
      resolve: () {
        final spend = 3 + rng.nextInt(4) * multiplier;
        return EventResult(
          coinDelta: 0,
          saveDelta: 0,
          spendDelta: spend,
          message: '소비했어요 -$spend 코인. 꼭 필요한 소비였나요?',
        );
      },
    ),
    EventCard(
      emoji: '🧹',
      title: '집안일 보상',
      description: '심부름을 도와 코인을 벌어요.',
      resolve: () {
        final gain = 4 + rng.nextInt(5) * multiplier;
        return EventResult(
          coinDelta: gain,
          saveDelta: 0,
          spendDelta: 0,
          message: '집안일 완료! +$gain 코인 획득.',
        );
      },
    ),
  ];
}
