// Copyright 2026 The Dawn & Tint Authors
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// 1. Redistributions of source code must retain the above copyright notice, this
//    list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright notice,
//    this list of conditions and the following disclaimer in the documentation
//    and/or other materials provided with the distribution.
//
// 3. Neither the name of the copyright holder nor the names of its
//    contributors may be used to endorse or promote products derived from
//    this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#include "src/tint/lang/msl/writer/raise/decompose_buffer.h"

#include <string>
#include <utility>

#include "src/tint/lang/core/fluent_types.h"
#include "src/tint/lang/core/ir/builder.h"
#include "src/tint/lang/core/ir/traverse.h"
#include "src/tint/lang/core/ir/validator.h"
#include "src/tint/lang/core/number.h"
#include "src/tint/lang/msl/builtin_fn.h"
#include "src/tint/lang/msl/ir/builtin_call.h"
#include "src/tint/utils/containers/hashmap.h"
#include "src/tint/utils/containers/hashset.h"

namespace tint::msl::writer::raise {
namespace {

using namespace tint::core::fluent_types;     // NOLINT
using namespace tint::core::number_suffixes;  // NOLINT

/// PIMPL state for the transform.
struct State {
    /// The IR module.
    core::ir::Module& ir;

    /// The IR builder.
    core::ir::Builder b{ir};

    /// The type manager.
    core::type::Manager& ty{ir.Types()};

    /// Tracks visited params.
    Hashset<core::ir::FunctionParam*, 16> visited_params_{};

    /// Tracks functions with updated parameter types
    Hashmap<core::ir::Function*, Hashset<size_t, 4>, 8> updated_func_args_{};

    /// Tracks function parameters used with arrayLength builtin functions.
    Hashmap<core::ir::FunctionParam*, bool, 16> used_with_array_length_{};

    /// Tracks buffer structs based on their pointer type.
    Hashmap<const core::type::Type*, const core::type::Struct*, 4> buffer_bundles_{};
    uint32_t bundle_name_suffix_ = 0;

    void Process() {
        LowerParameters();

        Vector<core::ir::Var*, 4> var_worklist;
        for (auto* inst : *ir.root_block) {
            auto* var = inst->As<core::ir::Var>();
            if (!var) {
                continue;
            }

            auto* var_ty = var->Result()->Type()->As<core::type::Pointer>();
            if (!var_ty) {
                continue;
            }

            // Only need to decompose buffers.
            if (var_ty->StoreType()->Is<core::type::Buffer>()) {
                var_worklist.Push(var);
            }
        }

        for (auto* var : var_worklist) {
            auto* result = var->Result();

            // Lower the variable type.
            auto* var_ty = result->Type()->As<core::type::Pointer>();
            const core::type::Type* arr_ty = nullptr;
            if (var_ty->UnwrapPtr()->HasFixedFootprint()) {
                arr_ty = ty.array(ty.u8(), var_ty->UnwrapPtr()->Size());
            } else {
                arr_ty = ty.runtime_array(ty.u8());
            }
            auto* new_ty = ty.ptr(var_ty->AddressSpace(), arr_ty, var_ty->Access());
            result->SetType(new_ty);

            TraverseUses(result, result->Type()->UnwrapPtr(), {});
        }
    }

    // Lowers buffer parameter types.
    //
    // buffer -> array<u8>
    // buffer<N> -> array<u8, N>
    //
    // Also fixes parameter mismatches by introducing a pointer offset call with zero offset as a
    // reinterpret cast.
    void LowerParameters() {
        auto ConvertType = [&](const core::type::Buffer* buffer,
                               const core::type::Pointer* pointer) {
            const core::type::Type* arr_ty = nullptr;
            if (buffer->Count()->Is<core::type::RuntimeArrayCount>()) {
                arr_ty = ty.runtime_array(ty.u8());
            } else {
                TINT_IR_ASSERT(ir, buffer->ConstantCount());
                arr_ty = ty.array(ty.u8(), buffer->ConstantCount().value());
            }
            return ty.ptr(pointer->AddressSpace(), arr_ty, pointer->Access());
        };

        auto ordered_funcs = ir.DependencyOrderedFunctions();
        for (auto func : ordered_funcs) {
            // Update mismatches.
            Traverse(func->Block(), [&](core::ir::UserCall* call) {
                auto* target = call->Target();
                size_t num_args = call->Args().size();
                for (size_t i = 0; i < num_args; i++) {
                    auto* param = target->Params()[i];
                    auto* arg = call->Args()[i];
                    if (auto* buf_ty = arg->Type()->UnwrapPtr()->As<core::type::Buffer>()) {
                        auto* ptr_ty = arg->Type()->As<core::type::Pointer>();
                        auto* converted_ty = ConvertType(buf_ty, ptr_ty);
                        if (converted_ty != param->Type()) {
                            b.InsertBefore(call, [&] {
                                auto* cast = b.CallExplicit<msl::ir::BuiltinCall>(
                                    param->Type(), msl::BuiltinFn::kPointerOffset,
                                    Vector{param->Type()->UnwrapPtr()}, arg, 0_u);
                                call->SetArg(i, cast->Result());
                            });
                        }
                    }
                }
            });

            // Lower buffer parameters.
            for (auto param : func->Params()) {
                if (auto* buf_ty = param->Type()->UnwrapPtr()->As<core::type::Buffer>()) {
                    auto* ptr_ty = param->Type()->As<core::type::Pointer>();
                    auto* new_ty = ConvertType(buf_ty, ptr_ty);
                    param->SetType(new_ty);

                    auto uses = param->UsagesSorted();
                    while (!uses.IsEmpty()) {
                        auto use = uses.Pop();
                        if (auto* let = use.instruction->As<core::ir::Let>()) {
                            let->Result()->SetType(new_ty);
                            for (auto& u : let->Result()->UsagesSorted()) {
                                uses.Push(u);
                            }
                        }
                    }
                }
            }
        }
    }

    struct OffsetData {
        uint32_t byte_offset = 0;
        // TODO(crbug.com/tint/472355939): a vector is strictly unnecessary if access traversal only
        // consider structs accessing a runtime array.
        Vector<core::ir::Value*, 4> byte_offset_expr{};

        // Struct offset is specifically to track offset post bufferView.
        uint32_t byte_struct_offset = 0;
        core::ir::Value* byte_struct_offset_expr = nullptr;

        // Only one bufferArrayView may be encountered so there can only be one size element.
        uint32_t byte_size = 0;
        core::ir::Value* byte_size_expr = nullptr;

        // Only one buffer[Array]View may be encountered so there can only be one length element.
        uint32_t byte_length = 0;
        core::ir::Value* byte_length_expr = nullptr;
    };

    // Note, must be called inside a builder insert block (Append, InsertBefore, etc)
    void UpdateOffsetData(core::ir::Value* offset, uint32_t elem_size, OffsetData* data) {
        tint::Switch(
            offset,  //
            [&](core::ir::Constant* idx_value) {
                data->byte_offset += idx_value->Value()->ValueAs<uint32_t>() * elem_size;
            },
            [&](core::ir::Value* val) {
                auto* idx = val;
                idx = b.InsertBitcastIfNeeded(ty.u32(), val);
                if (elem_size != 1) {
                    idx = b.Multiply(idx, u32(elem_size))->Result();
                }
                data->byte_offset_expr.Push(idx);
            },
            TINT_ICE_ON_NO_MATCH);
    }

    // Note, must be called inside a builder insert block (Append, InsertBefore, etc)
    // Note, size is always in bytes
    void UpdateSizeData(core::ir::Value* size, OffsetData* data) {
        tint::Switch(
            size,  //
            [&](core::ir::Constant* idx_value) {
                data->byte_size += idx_value->Value()->ValueAs<uint32_t>();
            },
            [&](core::ir::Value* val) {
                TINT_IR_ASSERT(ir, data->byte_size_expr == nullptr);
                data->byte_size_expr = b.InsertBitcastIfNeeded(ty.u32(), val);
            },
            TINT_ICE_ON_NO_MATCH);
    }

    // Note, must be called inside a builder insert block (Append, InsertBefore, etc)
    // Note, length is always in bytes
    void UpdateLengthData(core::ir::Value* length, OffsetData* data) {
        tint::Switch(
            length,  //
            [&](core::ir::Constant* idx_value) {
                data->byte_length += idx_value->Value()->ValueAs<uint32_t>();
            },
            [&](core::ir::Value* val) {
                TINT_IR_ASSERT(ir, data->byte_length_expr == nullptr);
                data->byte_length_expr = b.InsertBitcastIfNeeded(ty.u32(), val);
            },
            TINT_ICE_ON_NO_MATCH);
    }

    // Note, must be called inside a builder insert block (Append, InsertBefore, etc)
    core::ir::Value* OffsetToValue(const OffsetData& data) {
        core::ir::Value* value = nullptr;
        if (!data.byte_offset_expr.IsEmpty()) {
            TINT_IR_ASSERT(ir, data.byte_offset_expr.Length() == 1);
            value = data.byte_offset_expr[0];
            if (data.byte_offset != 0) {
                return b.Add(value, b.Constant(u32(data.byte_offset)))->Result();
            }
            return value;
        }
        return b.Constant(u32(data.byte_offset));
    }

    // Note, must be called inside a builder insert block (Append, InsertBefore, etc)
    core::ir::Value* StructOffsetToValue(const OffsetData& data) {
        core::ir::Value* value = nullptr;
        if (data.byte_struct_offset_expr) {
            value = data.byte_struct_offset_expr;
            if (data.byte_struct_offset != 0) {
                return b.Add(value, b.Constant(u32(data.byte_struct_offset)))->Result();
            }
            return value;
        }
        return b.Constant(u32(data.byte_struct_offset));
    }

    // Note, must be called inside a builder insert block (Append, InsertBefore, etc)
    core::ir::Value* SizeToValue(const OffsetData& data) {
        core::ir::Value* value = data.byte_size_expr;
        if (value) {
            if (data.byte_size != 0) {
                return b.Add(value, b.Constant(u32(data.byte_size)))->Result();
            }
            return value;
        }
        return b.Constant(u32(data.byte_size));
    }

    // Note, must be called inside a builder insert block (Append, InsertBefore, etc)
    core::ir::Value* LengthToValue(const OffsetData& data) {
        if (data.byte_length_expr) {
            TINT_IR_ASSERT(ir, data.byte_length == 0);
            return data.byte_length_expr;
        }
        return b.Constant(u32(data.byte_length));
    }

    // Transforms bufferLength calls.
    //
    // There are 3 cases
    // 1. The buffer length is encoded as an operand (from PropagateBufferSizes).
    // 2. The buffer type is a constant-sized buffer.
    // 3. The call needs replaced with an arrayLength call.
    //
    // @param call the bufferLength call
    void BufferLength(core::ir::CoreBuiltinCall* call) {
        auto* arr_ty = call->Args()[0]->Type()->UnwrapPtr()->As<core::type::Array>();
        TINT_IR_ASSERT(ir, call->Func() == core::BuiltinFn::kBufferLength);
        TINT_IR_ASSERT(
            ir,
            arr_ty &&
                (arr_ty->Count()
                     ->IsAnyOf<core::type::RuntimeArrayCount, core::type::ConstantArrayCount>()));

        if (call->Args().size() > 1) {
            // Length directly encoded during propagation.
            call->Result()->ReplaceAllUsesWith(call->Args()[1]);
        } else if (arr_ty->ConstantCount()) {
            call->Result()->ReplaceAllUsesWith(b.Constant(u32(arr_ty->ConstantCount().value())));
        } else {
            TINT_IR_ASSERT(ir, arr_ty->Count()->Is<core::type::RuntimeArrayCount>());
            b.InsertBefore(call, [&] {
                b.CallWithResult(call->DetachResult(), core::BuiltinFn::kArrayLength,
                                 call->Args()[0]);
            });
        }
        call->Destroy();
    }

    // Transforms bufferView and bufferArrayView calls
    //
    // Propagates the offset (and size) data from the call forward to the uses.
    // Replaces the call with a pointer offset call at the same offset.
    //
    // @param call The buffer[Array]View call
    void BufferView(core::ir::CoreBuiltinCall* call) {
        TINT_IR_ASSERT(ir, call->Func() == core::BuiltinFn::kBufferView ||
                               call->Func() == core::BuiltinFn::kBufferArrayView);
        OffsetData data;
        auto* offset_arg = call->Args()[1];
        core::ir::Instruction* new_call = nullptr;
        b.InsertBefore(call, [&] {
            offset_arg = b.InsertBitcastIfNeeded(ty.u32(), offset_arg);
            UpdateOffsetData(offset_arg, 1, &data);
            if (call->Func() == core::BuiltinFn::kBufferArrayView) {
                auto* size_arg = call->Args()[2];
                UpdateSizeData(size_arg, &data);
                if (call->Args().size() > 3) {
                    UpdateLengthData(call->Args()[3], &data);
                }
            } else if (call->Args().size() > 2) {
                UpdateLengthData(call->Args()[2], &data);
            }
            new_call = b.CallExplicitWithResult<msl::ir::BuiltinCall>(
                call->DetachResult(), msl::BuiltinFn::kPointerOffset,
                Vector{call->ExplicitTemplateParams()[0]}, call->Args()[0], offset_arg);
            call->Destroy();
        });

        TraverseUses(new_call->Result(), new_call->Result()->Type()->UnwrapPtr(), data);
    }

    // Process a pointer offset call.
    //
    // These should only be encountered as a result of `LowerParameters()`.
    //
    // @param call The call
    void PointerOffset(msl::ir::BuiltinCall* call) {
        // Should only encounter these due to parameter unification with 0
        // offset.
        TINT_IR_ASSERT(ir, call->Args()[1]->Is<core::ir::Constant>());
        TINT_IR_ASSERT(ir, call->Args()[1]->As<core::ir::Constant>()->Value()->AllZero());
        TraverseUses(call->Result(), call->Result()->Type()->UnwrapPtr(), {});
    }

    // Process an access instruction.
    //
    // Updates the offset data based on the indices.
    // The only interesting case is when there is an arrayLength call among the uses.
    //
    // @param a The access
    // @param type The type
    // @param data The offset data
    void Access(core::ir::Access* a, const core::type::Type* type, OffsetData data) {
        // Note, because we recurse through the `access` helper, the object passed in isn't
        // necessarily the originating `var` object, but maybe a partially resolved access chain
        // object.
        if (auto* view = type->As<core::type::MemoryView>()) {
            type = view->StoreType();
        }

        // Only need to traverse for types with a runtime-sized array
        if (a->Result()->Type()->UnwrapPtr()->HasFixedFootprint()) {
            return;
        }

        for (auto* idx_value : a->Indices()) {
            tint::Switch(
                type,
                [&](const core::type::Vector* v) {
                    b.InsertBefore(a,
                                   [&] { UpdateOffsetData(idx_value, v->Type()->Size(), &data); });
                    type = v->Type();
                },
                [&](const core::type::Matrix* m) {
                    b.InsertBefore(a,
                                   [&] { UpdateOffsetData(idx_value, m->ColumnStride(), &data); });
                    type = m->ColumnType();
                },
                [&](const core::type::Array* ary) {
                    b.InsertBefore(
                        a, [&] { UpdateOffsetData(idx_value, ary->ImplicitStride(), &data); });
                    type = ary->ElemType();
                },
                [&](const core::type::Struct* s) {
                    auto* cnst = idx_value->As<core::ir::Constant>();

                    // A struct index must be a constant
                    TINT_IR_ASSERT(ir, cnst);

                    uint32_t idx = cnst->Value()->ValueAs<uint32_t>();
                    auto* mem = s->Members()[idx];
                    type = mem->Type();
                    data.byte_struct_offset += mem->Offset();
                },
                TINT_ICE_ON_NO_MATCH);
        }

        TraverseUses(a->Result(), type, data);
    }

    // Traverse uses of `value`.
    //
    // Most uses are uninteresting and don't need handling.
    //
    // @param value The value
    // @param type The type
    // @param data The offset data
    void TraverseUses(core::ir::Value* value, const core::type::Type* type, OffsetData data) {
        auto usages = value->UsagesSorted();
        while (!usages.IsEmpty()) {
            auto usage = usages.Pop();

            // Don't need to handle too many parts of the usage chain.
            tint::Switch(
                usage.instruction,
                [&](core::ir::Let* let) {
                    for (auto& u : let->Result()->UsagesSorted()) {
                        usages.Push(u);
                    }
                    let->Result()->ReplaceAllUsesWith(value);
                    let->Destroy();
                },
                [&](core::ir::Access* access) { Access(access, type, data); },
                [&](core::ir::Construct* construct) {
                    TraverseUses(construct->Result(), construct->Result()->Type(), data);
                },
                [&](core::ir::UserCall* call) { UserCall(call, usage.operand_index, data); },
                [&](core::ir::CoreBuiltinCall* call) {
                    switch (call->Func()) {
                        case core::BuiltinFn::kBufferView:
                        case core::BuiltinFn::kBufferArrayView:
                            if (usage.operand_index == 0) {
                                // These should only be encountered via lowered parameters.
                                TINT_IR_ASSERT(ir, data.byte_offset == 0);
                                TINT_IR_ASSERT(ir, data.byte_offset_expr.IsEmpty());
                                TINT_IR_ASSERT(ir, data.byte_size == 0);
                                TINT_IR_ASSERT(ir, data.byte_size_expr == nullptr);
                                BufferView(call);
                            }
                            break;
                        case core::BuiltinFn::kBufferLength:
                            if (usage.operand_index == 0) {
                                // This should only be encountered via lowered parameters.
                                TINT_IR_ASSERT(ir, data.byte_offset == 0);
                                TINT_IR_ASSERT(ir, data.byte_offset_expr.IsEmpty());
                                TINT_IR_ASSERT(ir, data.byte_size == 0);
                                TINT_IR_ASSERT(ir, data.byte_size_expr == nullptr);
                                BufferLength(call);
                            }
                            break;
                        case core::BuiltinFn::kArrayLength:
                            ArrayLength(call, type, data);
                            break;
                        default:
                            break;
                    }
                },
                [&](msl::ir::BuiltinCall* call) {
                    if (call->Func() == msl::BuiltinFn::kPointerOffset &&
                        usage.operand_index == 0) {
                        PointerOffset(call);
                    }
                });
        }
    }

    // Process a user call.
    //
    // User calls are traversed to ensure all buffer_view related calls are handled. The call is
    // specially handled if the parameter for `operand_index` eventually is used by an
    // arrayLength builtin (though this is common with robustness enabled). The parameter is
    // replaced with a struct containing the pointer and two u32s for offset and size. All callsites
    // of `call->Target()` are updated on the first encounter. If subsequent callsites are visited
    // this function merely updates the offset and size values in the struct.
    //
    // @param call The call
    // @param operand_index The operand index of the parameter in the call (not arg index)
    // @param data The offset data
    void UserCall(core::ir::UserCall* call, size_t operand_index, OffsetData data) {
        size_t param_index = operand_index - call->ArgsOperandOffset();
        auto* target = call->Target();
        if (!UsedWithArrayLength(call, param_index)) {
            if (visited_params_.Add(target->Params()[param_index])) {
                // Don't construct the bundle struct, but continue looking.
                TraverseUses(call->Target()->Params()[param_index],
                             call->Args()[param_index]->Type()->UnwrapPtr(), data);
            }
            return;
        }

        // If this parameter has been encountered before, just update the offset and size values.
        core::ir::Value* param_value = nullptr;
        if (auto func_entry = updated_func_args_.Get(call->Target())) {
            if (func_entry->Contains(param_index)) {
                param_value = call->Args()[param_index];
                TINT_IR_ASSERT(ir, param_value->Type()->Is<core::type::Struct>());
                TINT_IR_ASSERT(ir, param_value->Is<core::ir::InstructionResult>());
                TINT_IR_ASSERT(ir, param_value->As<core::ir::InstructionResult>()
                                       ->Instruction()
                                       ->Is<core::ir::Construct>());
                auto* construct = param_value->As<core::ir::InstructionResult>()
                                      ->Instruction()
                                      ->As<core::ir::Construct>();
                b.InsertBefore(call, [&] {
                    auto* repl = b.Construct(param_value->Type(), construct->Args()[0],
                                             OffsetToValue(data), StructOffsetToValue(data),
                                             SizeToValue(data), LengthToValue(data));
                    param_value = repl->Result();
                    construct->Result()->ReplaceAllUsesWith(param_value);
                    construct->Destroy();
                });
                return;
            }
        }

        auto& entry =
            updated_func_args_.GetOrAddEntry(target, [&] { return Hashset<size_t, 4>{}; });
        entry.value.Add(param_index);

        // Check if we've generated a struct for this bundle (keyed on pointer) or generate a new
        // one.
        auto* target_param = target->Params()[param_index];
        auto* arg = call->Args()[param_index];
        const core::type::Struct* struct_ty =
            buffer_bundles_
                .GetOrAddEntry(arg->Type(),
                               [&] {
                                   return ty.Struct(
                                       ir.symbols.Register("buffer_bundle_" +
                                                           std::to_string(bundle_name_suffix_++)),
                                       {
                                           {ir.symbols.Register("buffer"), arg->Type()},
                                           {ir.symbols.Register("offset"), ty.u32()},
                                           {ir.symbols.Register("struct_offset"), ty.u32()},
                                           {ir.symbols.Register("size"), ty.u32()},
                                           {ir.symbols.Register("length"), ty.u32()},
                                       });
                               })
                .value;

        b.InsertBefore(call, [&] {
            param_value =
                b.Construct(struct_ty, arg, OffsetToValue(data), StructOffsetToValue(data),
                            SizeToValue(data), LengthToValue(data))
                    ->Result();
            call->SetArg(param_index, param_value);
            target_param->SetType(struct_ty);
        });
        // Update other calls to `target` with place holder offset and size.
        for (auto& use : target->UsagesSorted()) {
            auto* user = use.instruction->As<core::ir::UserCall>();
            if (user && user != call) {
                b.InsertBefore(user, [&] {
                    auto* construct =
                        b.Construct(struct_ty, user->Args()[param_index], 0_u, 0_u, 0_u, 0_u);
                    user->SetArg(param_index, construct->Result());
                });
            }
        }

        // Unpack the bundle in the target function and update the original parameter's uses to use
        // the 0'th element of the struct.
        core::ir::Instruction* access = nullptr;
        core::ir::Value* offset = nullptr;
        core::ir::Value* struct_offset = nullptr;
        core::ir::Value* size = nullptr;
        core::ir::Value* length = nullptr;
        b.InsertBefore(target->Block()->Front(), [&] {
            access = b.Access(arg->Type(), target_param, b.Constant(0_u));
            target_param->ReplaceAllUsesWith(access->Result());
            access->SetOperand(0, target_param);
            offset = b.Access(ty.u32(), target_param, b.Constant(1_u))->Result();
            struct_offset = b.Access(ty.u32(), target_param, b.Constant(2_u))->Result();
            size = b.Access(ty.u32(), target_param, b.Constant(3_u))->Result();
            length = b.Access(ty.u32(), target_param, b.Constant(4_u))->Result();
        });

        // Continue the traversal from the access in target with offset data based on the unpacked
        // offset and size.
        OffsetData new_data{.byte_offset_expr{offset},
                            .byte_struct_offset_expr = struct_offset,
                            .byte_size_expr = size,
                            .byte_length_expr = length};
        TraverseUses(access->Result(), arg->Type()->UnwrapPtr(), new_data);
    }

    // Checks if the parameter is used with an arrayLength builtin.
    //
    // @param call The call
    // @param param_index The parameter index
    // @returns true if param_index in `call->Target()` is eventually used with arrayLength
    bool UsedWithArrayLength(core::ir::UserCall* call, size_t param_index) {
        auto* target = call->Target();
        auto* param = target->Params()[param_index];
        if (auto entry = used_with_array_length_.Get(param)) {
            return *entry.value;
        }

        auto usage = param->UsagesSorted();
        while (!usage.IsEmpty()) {
            auto use = usage.Pop();
            auto found = tint::Switch(
                use.instruction,
                [&](core::ir::Let* let) {
                    for (auto& u : let->Result()->UsagesUnsorted()) {
                        usage.Push(u);
                    }
                    return false;
                },
                [&](core::ir::Access* access) {
                    for (auto& u : access->Result()->UsagesUnsorted()) {
                        usage.Push(u);
                    }
                    return false;
                },
                [&](core::ir::Construct* construct) {
                    for (auto& u : construct->Result()->UsagesUnsorted()) {
                        usage.Push(u);
                    }
                    return false;
                },
                [&](core::ir::CoreBuiltinCall* builtin) {
                    if (builtin->Func() == core::BuiltinFn::kArrayLength) {
                        return true;
                    }
                    return false;
                },
                [&](core::ir::UserCall* user) {
                    return UsedWithArrayLength(user, use.operand_index - call->ArgsOperandOffset());
                },
                [&](msl::ir::BuiltinCall* builtin) {
                    if (builtin->Func() == msl::BuiltinFn::kPointerOffset) {
                        for (auto& u : builtin->Result()->UsagesUnsorted()) {
                            usage.Push(u);
                        }
                    }
                    return false;
                },
                [&](Default) { return false; });
            if (found) {
                used_with_array_length_.Add(param, true);
                return true;
            }
        }

        used_with_array_length_.Add(param, false);
        return false;
    }

    // Updates an arrayLength call to account for `offset`.
    // The builtin call returns the length of the whole variable. The array type may have changed
    // too, so we must account for that difference. Any offset must be subtracted from that value to
    // provide the same result as before the transform. Offsets can come from two sources:
    //
    // 1. An offset from an access into a structure.
    // 2. An offset (possibly runtime value) from a bufferView call.
    //
    // Additionally, the size may be constrained from a bufferArrayView call.
    // If the size members in `data` are non-zero we use that as a starting point instead of the
    // builtin call.
    void ArrayLength(core::ir::CoreBuiltinCall* call,
                     const core::type::Type* type,
                     OffsetData data) {
        auto address_space = call->Args()[0]->Type()->As<core::type::Pointer>()->AddressSpace();
        auto* array_ty = type->As<core::type::Array>();
        TINT_IR_ASSERT(ir, array_ty && array_ty->Count()->Is<core::type::RuntimeArrayCount>());

        // Buffers are always in bytes.
        const uint32_t ratio = array_ty->ImplicitStride();

        // Given:
        // b = bufferArrayView var, offset1, size
        // a = access b, offset2
        // l = arrayLength a
        //
        //
        // Transformed:
        // buf_len = data.length
        // arr_len = arrayLength var
        // len = select(buf_len, arr_len, buf_len == 0)
        // l = select(size, len, size == 0)
        // o1 = select(0, offset1, size == 0)
        // s1 = sub l, o1
        // s2 = sub s1, offset2
        // d = div s2, ratio
        b.InsertBefore(call, [&] {
            // Re-create the arrayLength call to simplify RAUW below.
            // Uniform and workgroup buffers are guaranteed to be sized so it is unnecessary there
            // (and array length doesn't work).
            core::ir::Value* len = LengthToValue(data);
            if (address_space != core::AddressSpace::kUniform &&
                address_space != core::AddressSpace::kWorkgroup) {
                // If the length was encoded earlier use that over arrayLength because it handles
                // buffers shrunk via parameter conversion.
                auto* array_len =
                    b.Call(ty.u32(), core::BuiltinFn::kArrayLength, call->Args()[0])->Result();
                auto* len_cmp = b.Equal(len, 0_u);
                len = b.Call(ty.u32(), core::BuiltinFn::kSelect, len, array_len, len_cmp)->Result();
            }
            core::ir::Value* size = SizeToValue(data);
            auto* cmp = b.Equal(size, 0_u);
            if (auto cnst = size->As<core::ir::Constant>()) {
                if (cnst->Value()->ValueAs<uint32_t>() != 0) {
                    len = b.Call(ty.u32(), core::BuiltinFn::kSelect, size, len, cmp->Result())
                              ->Result();
                }
            } else {
                len =
                    b.Call(ty.u32(), core::BuiltinFn::kSelect, size, len, cmp->Result())->Result();
            }

            core::ir::Value* offset = OffsetToValue(data);
            if (offset) {
                auto* sub_val =
                    b.Call(ty.u32(), core::BuiltinFn::kSelect, 0_u, offset, cmp->Result());
                len = b.Subtract(len, sub_val->Result())->Result();
            }
            core::ir::Value* struct_offset = StructOffsetToValue(data);
            if (struct_offset) {
                len = b.Subtract(len, struct_offset)->Result();
            }
            if (ratio != 1u) {
                len = b.Divide(len, u32(ratio))->Result();
            }
            call->Result()->ReplaceAllUsesWith(len);
        });
        call->Destroy();
    }
};

}  // namespace

Result<SuccessType> DecomposeBuffer(core::ir::Module& ir) {
    AssertValid(ir,
                tint::core::ir::Capabilities{
                    tint::core::ir::Capability::kAllowPointSizeBuiltin,
                    tint::core::ir::Capability::kAllowDuplicateBindings,
                },
                "before msl.DecomposeBuffer");

    State{ir}.Process();

    return Success;
}

}  // namespace tint::msl::writer::raise
