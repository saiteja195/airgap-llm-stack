#!/usr/bin/env bash
# Cut the kind nodes off from the internet (node-level air gap). Traffic inside the Docker network still works.
# This is the demo's stand-in for a customer's physical network boundary; the chart's NetworkPolicies are a second layer.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
need docker
NET="${KIND_NETWORK:-kind}"
CLUSTER_CIDRS="${CLUSTER_CIDRS:-10.244.0.0/16 10.96.0.0/16}"   # kind defaults: pod and service CIDRs
SUBNETS="$(docker network inspect "$NET" -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}')"
for node in $(docker ps --filter "label=io.x-k8s.kind.cluster=$CLUSTER" --format '{{.Names}}'); do
  for subnet in $SUBNETS; do
    case "$subnet" in *:*) ipt=ip6tables ;; *) ipt=iptables ;; esac
    docker exec "$node" "$ipt" -w -I FORWARD -o eth0 ! -d "$subnet" -j DROP 2>/dev/null || true
    docker exec "$node" "$ipt" -w -I OUTPUT ! -d "$subnet" ! -o lo -j DROP 2>/dev/null || true
  done
  # In-cluster traffic (pod -> API server via the service IP, pod -> pod) must keep flowing; only the outside is cut off.
  for cidr in $CLUSTER_CIDRS; do
    docker exec "$node" iptables -w -I FORWARD -d "$cidr" -j ACCEPT
    docker exec "$node" iptables -w -I OUTPUT -d "$cidr" -j ACCEPT
  done
  log "egress blocked on $node (allowed: $SUBNETS)"
done
