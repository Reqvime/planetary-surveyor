// Locate the known PopulateDiscoveryInfo pattern and report its direct calls.
// @category NMSDiscoveryLab

import java.util.ArrayList;
import java.util.Map;
import java.util.TreeMap;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;

public class InspectPopulateDiscoveryInfo extends GhidraScript {
    private static final String POPULATE_PATTERN =
        "48 8B C4 4C 89 48 ? 44 89 40 ? 48 89 48";

    private static class PatternBytes {
        final byte[] values;
        final byte[] masks;

        PatternBytes(byte[] values, byte[] masks) {
            this.values = values;
            this.masks = masks;
        }
    }

    @Override
    protected void run() throws Exception {
        PatternBytes pattern = parsePattern(POPULATE_PATTERN);
        ArrayList<Address> hits = findAll(pattern);
        StringBuilder report = new StringBuilder();

        append(report, "NMS_DISCOVERY_REPORT_BEGIN");
        append(report, "pattern=" + POPULATE_PATTERN);
        append(report, "match_count=" + hits.size());

        if (hits.size() != 1) {
            append(report, "status=ERROR_EXPECTED_ONE_MATCH");
            append(report, "NMS_DISCOVERY_REPORT_END");
            publishReport(report.toString());
            return;
        }

        Address hit = hits.get(0);
        FunctionManager functionManager = currentProgram.getFunctionManager();
        Function function = functionManager.getFunctionContaining(hit);
        if (function == null) {
            append(report, "match_address=" + hit);
            append(report, "status=ERROR_NO_CONTAINING_FUNCTION");
            append(report, "NMS_DISCOVERY_REPORT_END");
            publishReport(report.toString());
            return;
        }

        append(report, "status=OK");
        append(report, "match_address=" + hit);
        append(report, "function_entry=" + function.getEntryPoint());
        append(report, "function_name=" + function.getName());
        append(report, "function_size=" + function.getBody().getNumAddresses());

        TreeMap<Address, Function> directCalls = collectDirectCalls(function);
        append(report, "direct_call_count=" + directCalls.size());
        for (Map.Entry<Address, Function> entry : directCalls.entrySet()) {
            Function called = entry.getValue();
            append(report,
                "call_site=" + entry.getKey() +
                " target=" + called.getEntryPoint() +
                " name=" + called.getName() +
                " size=" + called.getBody().getNumAddresses()
            );
        }

        append(report, "decompile_begin");
        append(report, decompile(function));
        append(report, "decompile_end");
        append(report, "NMS_DISCOVERY_REPORT_END");
        publishReport(report.toString());
    }

    private void append(StringBuilder report, String line) {
        report.append(line).append(System.lineSeparator());
    }

    private void publishReport(String report) throws Exception {
        String[] args = getScriptArgs();
        if (args.length > 0 && !args[0].isBlank()) {
            Path output = Path.of(args[0]);
            Files.createDirectories(output.getParent());
            Files.writeString(output, report, StandardCharsets.UTF_8);
            println("report_file=" + output);
        }
        else {
            println(report);
        }
    }

    private PatternBytes parsePattern(String text) {
        String[] tokens = text.trim().split("\\s+");
        byte[] values = new byte[tokens.length];
        byte[] masks = new byte[tokens.length];
        for (int i = 0; i < tokens.length; i++) {
            if (tokens[i].equals("?") || tokens[i].equals("??")) {
                values[i] = 0;
                masks[i] = 0;
            }
            else {
                values[i] = (byte) Integer.parseInt(tokens[i], 16);
                masks[i] = (byte) 0xff;
            }
        }
        return new PatternBytes(values, masks);
    }

    private ArrayList<Address> findAll(PatternBytes pattern) {
        ArrayList<Address> hits = new ArrayList<>();
        Memory memory = currentProgram.getMemory();
        Address end = currentProgram.getMaxAddress();
        Address cursor = currentProgram.getMinAddress();

        while (cursor != null && cursor.compareTo(end) <= 0 && !monitor.isCancelled()) {
            Address hit = memory.findBytes(cursor, end, pattern.values, pattern.masks, true, monitor);
            if (hit == null) {
                break;
            }
            hits.add(hit);
            cursor = hit.next();
        }
        return hits;
    }

    private TreeMap<Address, Function> collectDirectCalls(Function function) {
        TreeMap<Address, Function> calls = new TreeMap<>();
        Listing listing = currentProgram.getListing();
        FunctionManager functionManager = currentProgram.getFunctionManager();
        InstructionIterator instructions = listing.getInstructions(function.getBody(), true);

        while (instructions.hasNext() && !monitor.isCancelled()) {
            Instruction instruction = instructions.next();
            for (Reference reference : instruction.getReferencesFrom()) {
                if (!reference.getReferenceType().isCall()) {
                    continue;
                }
                Function called = functionManager.getFunctionAt(reference.getToAddress());
                if (called != null) {
                    calls.put(instruction.getAddress(), called);
                }
            }
        }
        return calls;
    }

    private String decompile(Function function) {
        DecompInterface decompiler = new DecompInterface();
        try {
            decompiler.openProgram(currentProgram);
            DecompileResults results = decompiler.decompileFunction(function, 120, monitor);
            if (!results.decompileCompleted()) {
                return "DECOMPILE_ERROR: " + results.getErrorMessage();
            }
            return results.getDecompiledFunction().getC();
        }
        finally {
            decompiler.dispose();
        }
    }
}
