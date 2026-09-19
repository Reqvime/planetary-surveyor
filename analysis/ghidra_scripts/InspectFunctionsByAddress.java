// Report bytes, callers, callees, and decompilation for specified function addresses.
// First argument is the output path; remaining arguments are addresses.
// @category NMSDiscoveryLab

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class InspectFunctionsByAddress extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            throw new IllegalArgumentException(
                "Expected output path followed by at least one function address"
            );
        }

        StringBuilder report = new StringBuilder();
        append(report, "NMS_FUNCTION_REPORT_BEGIN");
        for (int i = 1; i < args.length; i++) {
            inspectAddress(args[i], report);
        }
        append(report, "NMS_FUNCTION_REPORT_END");

        Path output = Path.of(args[0]);
        Files.createDirectories(output.getParent());
        Files.writeString(output, report.toString(), StandardCharsets.UTF_8);
        println("report_file=" + output);
    }

    private void inspectAddress(String addressText, StringBuilder report) throws Exception {
        Address requested = currentProgram.getAddressFactory().getAddress(addressText);
        FunctionManager functionManager = currentProgram.getFunctionManager();
        Function function = functionManager.getFunctionContaining(requested);

        append(report, "function_report_begin requested=" + addressText);
        if (function == null) {
            append(report, "status=ERROR_NO_CONTAINING_FUNCTION");
            append(report, "function_report_end");
            return;
        }

        append(report, "status=OK");
        append(report, "entry=" + function.getEntryPoint());
        append(report, "name=" + function.getName());
        append(report, "size=" + function.getBody().getNumAddresses());
        append(report, "entry_bytes=" + readBytes(function.getEntryPoint(), 64));

        TreeSet<Address> callers = collectCallers(function);
        append(report, "caller_count=" + callers.size());
        for (Address caller : callers) {
            Function callerFunction = functionManager.getFunctionContaining(caller);
            append(
                report,
                "caller_site=" + caller +
                " caller_entry=" +
                (callerFunction == null ? "UNKNOWN" : callerFunction.getEntryPoint()) +
                " caller_name=" +
                (callerFunction == null ? "UNKNOWN" : callerFunction.getName())
            );
        }

        TreeMap<Address, Function> calls = collectDirectCalls(function);
        append(report, "direct_call_count=" + calls.size());
        for (Map.Entry<Address, Function> entry : calls.entrySet()) {
            Function called = entry.getValue();
            append(
                report,
                "call_site=" + entry.getKey() +
                " target=" + called.getEntryPoint() +
                " name=" + called.getName() +
                " size=" + called.getBody().getNumAddresses()
            );
        }

        append(report, "decompile_begin");
        append(report, decompile(function));
        append(report, "decompile_end");
        append(report, "function_report_end");
    }

    private String readBytes(Address start, int count) throws Exception {
        byte[] bytes = new byte[count];
        int read = currentProgram.getMemory().getBytes(start, bytes);
        StringBuilder text = new StringBuilder();
        for (int i = 0; i < read; i++) {
            if (i > 0) text.append(' ');
            text.append(String.format("%02X", bytes[i] & 0xff));
        }
        return text.toString();
    }

    private TreeSet<Address> collectCallers(Function function) {
        TreeSet<Address> callers = new TreeSet<>();
        ReferenceIterator references = currentProgram.getReferenceManager()
            .getReferencesTo(function.getEntryPoint());
        while (references.hasNext() && !monitor.isCancelled()) {
            Reference reference = references.next();
            if (reference.getReferenceType().isCall()) {
                callers.add(reference.getFromAddress());
            }
        }
        return callers;
    }

    private TreeMap<Address, Function> collectDirectCalls(Function function) {
        TreeMap<Address, Function> calls = new TreeMap<>();
        Listing listing = currentProgram.getListing();
        FunctionManager functionManager = currentProgram.getFunctionManager();
        InstructionIterator instructions = listing.getInstructions(function.getBody(), true);

        while (instructions.hasNext() && !monitor.isCancelled()) {
            Instruction instruction = instructions.next();
            for (Reference reference : instruction.getReferencesFrom()) {
                if (!reference.getReferenceType().isCall()) continue;
                Function called = functionManager.getFunctionAt(reference.getToAddress());
                if (called != null) calls.put(instruction.getAddress(), called);
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

    private void append(StringBuilder report, String line) {
        report.append(line).append(System.lineSeparator());
    }
}
