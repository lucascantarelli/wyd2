//! Janela deslizante de falhas de login, por IP e por conta.
//!
//! Conta apenas falhas de autenticacao (conta inexistente ou senha errada);
//! login bem-sucedido limpa a chave da conta. O estado vive no processo: um
//! reinicio do gateway zera a janela. O objetivo e frear forca bruta e
//! enumeracao, nao substituir um WAF.

use std::collections::{HashMap, VecDeque};
use std::time::{Duration, Instant};

/// Teto de chaves rastreadas; ao passar disso, a chave mais antiga sai.
const MAX_TRACKED_KEYS: usize = 4096;

pub struct FailureWindow {
    limit: u32,
    window: Duration,
    failures: HashMap<String, VecDeque<Instant>>,
}

impl FailureWindow {
    pub fn new(limit: u32, window: Duration) -> Self {
        Self {
            limit: limit.max(1),
            window,
            failures: HashMap::new(),
        }
    }

    /// Tempo restante de bloqueio para `key`, ou `None` se ainda ha margem.
    pub fn blocked_for(&mut self, key: &str, now: Instant) -> Option<Duration> {
        self.prune(now);
        let queue = self.failures.get(key)?;
        if (queue.len() as u32) < self.limit {
            return None;
        }
        let oldest = *queue.front()?;
        Some(
            self.window
                .saturating_sub(now.saturating_duration_since(oldest)),
        )
    }

    /// Registra uma falha de autenticacao para `key`.
    pub fn record(&mut self, key: &str, now: Instant) {
        self.prune(now);
        self.failures
            .entry(key.to_owned())
            .or_default()
            .push_back(now);
        self.evict_overflow();
    }

    pub fn clear(&mut self, key: &str) {
        self.failures.remove(key);
    }

    /// Chaves com falhas dentro da janela; usado nos testes de limite.
    pub fn tracked_keys(&self) -> usize {
        self.failures.len()
    }

    fn prune(&mut self, now: Instant) {
        let window = self.window;
        self.failures.retain(|_, queue| {
            while queue
                .front()
                .is_some_and(|first| now.saturating_duration_since(*first) >= window)
            {
                queue.pop_front();
            }
            !queue.is_empty()
        });
    }

    fn evict_overflow(&mut self) {
        if self.failures.len() <= MAX_TRACKED_KEYS {
            return;
        }
        let oldest = self
            .failures
            .iter()
            .min_by_key(|(_, queue)| queue.back().copied())
            .map(|(key, _)| key.clone());
        if let Some(key) = oldest {
            self.failures.remove(&key);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn window(limit: u32) -> FailureWindow {
        FailureWindow::new(limit, Duration::from_secs(60))
    }

    #[test]
    fn bloqueia_so_depois_do_limite() {
        let mut failures = window(2);
        let start = Instant::now();
        let key = "ip:127.0.0.1";

        assert!(failures.blocked_for(key, start).is_none());
        failures.record(key, start);
        assert!(failures.blocked_for(key, start).is_none());
        failures.record(key, start + Duration::from_secs(5));
        assert!(failures
            .blocked_for(key, start + Duration::from_secs(6))
            .is_some());
    }

    #[test]
    fn libera_quando_a_janela_expira() {
        let mut failures = window(1);
        let start = Instant::now();
        let key = "account:testaccount";
        failures.record(key, start);

        assert!(failures
            .blocked_for(key, start + Duration::from_secs(59))
            .is_some());
        assert!(failures
            .blocked_for(key, start + Duration::from_secs(60))
            .is_none());
        assert_eq!(failures.tracked_keys(), 0);
    }

    #[test]
    fn chaves_sao_independentes_e_clear_libera() {
        let mut failures = window(1);
        let start = Instant::now();
        failures.record("ip:10.0.0.1", start);
        assert!(failures.blocked_for("ip:10.0.0.1", start).is_some());
        assert!(failures.blocked_for("ip:10.0.0.2", start).is_none());

        failures.clear("ip:10.0.0.1");
        assert!(failures.blocked_for("ip:10.0.0.1", start).is_none());
    }

    #[test]
    fn mapa_nao_cresce_alem_do_teto() {
        let mut failures = window(1);
        let start = Instant::now();
        for index in 0..(MAX_TRACKED_KEYS + 10) {
            failures.record(&format!("conta-{index}"), start);
        }
        assert_eq!(failures.tracked_keys(), MAX_TRACKED_KEYS);
    }
}
